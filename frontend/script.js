document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');

    // Sections
    const uploadSection = document.getElementById('upload-section');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');

    // Videos
    const rawVideo = document.getElementById('raw-video');
    const processedVideo = document.getElementById('processed-video');

    // Actions
    const resetBtn = document.getElementById('reset-btn');
    const downloadBtn = document.getElementById('download-btn');

    // Section Management
    function showSection(section) {
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        section.classList.add('active');
    }

    // File Input Trigger
    browseBtn.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('click', (e) => {
        if (e.target !== browseBtn) fileInput.click();
    });

    // Drag and Drop Events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    });

    fileInput.addEventListener('change', function () {
        handleFiles(this.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;
        const file = files[0];

        // Basic validation
        if (!file.type.startsWith('video/')) {
            alert('Please upload a valid video file.');
            return;
        }

        uploadVideo(file);
    }

    async function uploadVideo(file) {
        showSection(processingSection);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/v1/stabilize', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Stabilization failed');
            }

            const data = await response.json();

            // Set video sources
            rawVideo.src = data.original_video_url;
            processedVideo.src = data.stabilized_video_url;

            // Set download link
            downloadBtn.href = data.stabilized_video_url;

            // Show results
            showSection(resultsSection);

            // Sync playback behavior (optional enhancement)
            syncVideos();

        } catch (error) {
            alert('Error: ' + error.message);
            showSection(uploadSection);
        }
    }

    function syncVideos() {
        rawVideo.addEventListener('play', () => processedVideo.play());
        rawVideo.addEventListener('pause', () => processedVideo.pause());
        rawVideo.addEventListener('seeked', () => {
            processedVideo.currentTime = rawVideo.currentTime;
        });

        // Unmute processed but keep raw muted so we only hear one audio track if any.
        // Or keep both muted if it's purely a visual demo.
    }

    resetBtn.addEventListener('click', () => {
        rawVideo.src = '';
        processedVideo.src = '';
        fileInput.value = '';
        showSection(uploadSection);
    });
});
