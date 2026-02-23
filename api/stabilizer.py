import cv2
import numpy as np
import time
from scipy.ndimage import gaussian_filter1d
import os
import subprocess

class TranslationStabilizer:
    """
    Stabilizer that ONLY corrects translation (x, y shifts).
    Completely ignores rotation to prevent spinning artifacts.
    Refactored for FastAPI Backend (No OpenCV UI calls).
    """

    def __init__(self, smoothing_window=60, max_features=500):
        self.smoothing_window = smoothing_window
        self.max_features = max_features

        # Use SIFT for better feature tracking (if available)
        try:
            self.detector = cv2.SIFT_create(nfeatures=max_features)
            self.use_sift = True
        except:
            self.detector = cv2.ORB_create(nfeatures=max_features)
            self.use_sift = False

        if self.use_sift:
            self.matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        else:
            self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def detect_and_match_features(self, prev_gray, curr_gray):
        """Detect and match features between frames."""
        kp1, des1 = self.detector.detectAndCompute(prev_gray, None)
        kp2, des2 = self.detector.detectAndCompute(curr_gray, None)

        if des1 is None or des2 is None or len(des1) < 10:
            return None, None

        # Match features
        matches = self.matcher.knnMatch(des1, des2, k=2)

        # Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)

        if len(good_matches) < 10:
            return None, None

        # Extract point coordinates
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        return src_pts, dst_pts

    def estimate_translation(self, src_pts, dst_pts):
        """Estimate ONLY translation (dx, dy) using median of point movements."""
        if src_pts is None or dst_pts is None:
            return 0, 0

        displacements = dst_pts - src_pts
        dx = np.median(displacements[:, :, 0])
        dy = np.median(displacements[:, :, 1])
        return dx, dy

    def smooth_trajectory(self, trajectory):
        """Apply Gaussian smoothing to trajectory."""
        smoothed = np.copy(trajectory)
        sigma = self.smoothing_window / 3.0
        smoothed[:, 0] = gaussian_filter1d(trajectory[:, 0], sigma=sigma)
        smoothed[:, 1] = gaussian_filter1d(trajectory[:, 1], sigma=sigma)
        return smoothed

    def stabilize(self, input_path, output_path, crop_ratio=0.90):
        """
        Stabilize video by correcting translation only.
        Writes output and returns the output path upon completion.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Missing input video: {input_path}")

        cap = cv2.VideoCapture(input_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps == 0 or n_frames == 0:
            raise ValueError("Invalid video file")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        temp_output_path = output_path.replace(".mp4", "_temp.mp4")
        out = cv2.VideoWriter(temp_output_path, fourcc, fps, (width, height))

        ret, prev_frame = cap.read()
        if not ret:
            raise ValueError("Could not read first frame")

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        transforms = []

        # 1. Track Camera Motion
        while True:
            ret, curr_frame = cap.read()
            if not ret:
                break

            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
            src_pts, dst_pts = self.detect_and_match_features(prev_gray, curr_gray)
            dx, dy = self.estimate_translation(src_pts, dst_pts)
            transforms.append([dx, dy])

            prev_gray = curr_gray

        transforms = np.array(transforms)

        if len(transforms) == 0:
            raise ValueError("Could not compute motion transforms")

        # 2. Compute smooth path
        trajectory = np.cumsum(transforms, axis=0)
        smoothed_trajectory = self.smooth_trajectory(trajectory)
        difference = smoothed_trajectory - trajectory
        transforms_smooth = transforms + difference

        # 3. Apply Stabilization
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        for i in range(len(transforms_smooth)):
            ret, frame = cap.read()
            if not ret:
                break

            dx, dy = transforms_smooth[i]
            T = np.float32([[1, 0, dx], [0, 1, dy]])

            frame_stabilized = cv2.warpAffine(
                frame, T, (width, height), borderMode=cv2.BORDER_REPLICATE
            )

            crop_h = int(height * crop_ratio)
            crop_w = int(width * crop_ratio)
            border_h = (height - crop_h) // 2
            border_w = (width - crop_w) // 2

            frame_cropped = frame_stabilized[
                border_h:border_h + crop_h, border_w:border_w + crop_w
            ]
            frame_final = cv2.resize(frame_cropped, (width, height))
            out.write(frame_final)

        cap.release()
        out.release()
        
        # Convert to H.264 for HTML5 compatibility
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", temp_output_path,
                "-vcodec", "libx264", output_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        except Exception as e:
            print(f"FFmpeg conversion failed: {e}")
            if os.path.exists(temp_output_path):
                os.rename(temp_output_path, output_path)
        
        return output_path
