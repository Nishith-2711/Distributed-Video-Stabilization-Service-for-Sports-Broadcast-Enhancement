document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');
    const jobList = document.getElementById('job-list');

    // File Input Trigger
    browseBtn.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('click', (e) => {
        if (e.target !== browseBtn) fileInput.click();
    });

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
        
        // iterate to support multiple files eventually, but process one-by-one
        for(let i=0; i<files.length; i++) {
            const file = files[i];
            if (!file.type.startsWith('video/')) {
                alert(`File ${file.name} is not a valid video.`);
                continue;
            }
            uploadVideo(file);
        }
    }

    async function uploadVideo(file) {
        // Create initial job card UI
        const cardId = 'job-' + Date.now();
        const card = document.createElement('div');
        card.id = cardId;
        card.className = 'job-card';
        card.innerHTML = `
            <div class="job-header">
                <strong>${file.name}</strong>
                <span class="status-badge" id="badge-${cardId}">Uploading...</span>
            </div>
            <div class="job-body" id="body-${cardId}">
                <div class="spinner"></div>
            </div>
        `;
        jobList.prepend(card);

        const badge = document.getElementById(`badge-${cardId}`);
        const body = document.getElementById(`body-${cardId}`);

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
            const jobId = data.job_id;

            badge.innerText = 'Queued';

            // Poll for status
            let jobStatus = data.status;
            let jobData = data;
            
            while (jobStatus === "queued" || jobStatus === "processing") {
                await new Promise(resolve => setTimeout(resolve, 2000));
                badge.innerText = jobStatus === "processing" ? "Stabilizing..." : "Queued";
                
                const statusResponse = await fetch(`/api/v1/status/${jobId}`);
                if (!statusResponse.ok) {
                    throw new Error("Failed to check status");
                }
                jobData = await statusResponse.json();
                jobStatus = jobData.status;

                if (jobStatus === "failed") {
                    throw new Error(jobData.error || 'Video processing failed');
                }
            }

            // Completed! Update the card to show results
            badge.innerText = 'Completed';
            badge.classList.add('success');
            
            const rawUrl = `/api/v1/video/raw/${jobData.input_video}`;
            const processedUrl = `/api/v1/video/processed/${jobData.output_video}`;

            body.innerHTML = `
                <div class="comparison-container-small">
                    <div>
                        <div style="font-size: 0.8rem; margin-bottom: 4px;">Original</div>
                        <video src="${rawUrl}" controls muted loop style="width:100%; border-radius: 8px; border: 1px solid #334155;"></video>
                    </div>
                    <div>
                        <div style="font-size: 0.8rem; margin-bottom: 4px; color: #10b981;">Stabilized</div>
                        <video src="${processedUrl}" controls muted loop style="width:100%; border-radius: 8px; border: 1px solid #334155;"></video>
                    </div>
                </div>
                <div style="margin-top: 10px; display: flex; justify-content: flex-end;">
                    <a href="${processedUrl}" download class="btn primary" style="padding: 0.5rem 1rem; font-size: 0.9rem;">Download Stabilized</a>
                </div>
            `;

            // Auto-play sync for this specific card
            const videos = body.querySelectorAll('video');
            if (videos.length === 2) {
                const [v1, v2] = videos;
                v1.addEventListener('play', () => v2.play());
                v1.addEventListener('pause', () => v2.pause());
                v1.addEventListener('seeked', () => { v2.currentTime = v1.currentTime; });
            }

        } catch (error) {
            badge.innerText = 'Failed';
            badge.classList.add('error');
            body.innerHTML = `<p style="color: #ef4444; font-size: 0.9rem;">${error.message}</p>`;
        }
    }
});
