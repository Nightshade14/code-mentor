document.addEventListener('DOMContentLoaded', () => {
    const submitBtn = document.getElementById('submitBtn');
    const repoInput = document.getElementById('repoUrl');
    const resultSection = document.getElementById('result-section');
    const archImage = document.getElementById('archImage');
    const errorMessage = document.getElementById('error-message');

    const enhanceBtn = document.getElementById('enhanceBtn');
    let currentKnowledge = null;

    // API Base URL - change this if your server runs on a different port
    const API_BASE_URL = 'http://localhost:8000';

    submitBtn.addEventListener('click', async () => {
        const repoPath = repoInput.value.trim();

        if (!repoPath) {
            showError('Please enter a repository URL or path');
            return;
        }

        // Reset state
        hideError();
        resultSection.classList.add('hidden');
        enhanceBtn.classList.add('hidden');
        submitBtn.classList.add('loading');
        submitBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE_URL}/extract_knowledge`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ repo_path: repoPath }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to process repository');
            }

            const data = await response.json();

            // Update image
            updateImage(data.diagram_path);

            // Show result and enhance button
            resultSection.classList.remove('hidden');
            enhanceBtn.classList.remove('hidden');

        } catch (error) {
            console.error('Error:', error);
            showError(error.message);
        } finally {
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
        }
    });

    enhanceBtn.addEventListener('click', async () => {
        enhanceBtn.classList.add('loading');
        enhanceBtn.disabled = true;
        hideError();

        try {
            const response = await fetch(`${API_BASE_URL}/enhance_diagram`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to enhance diagram');
            }

            const data = await response.json();
            updateImage(data.diagram_path);

        } catch (error) {
            console.error('Enhancement Error:', error);
            showError(error.message);
        } finally {
            enhanceBtn.classList.remove('loading');
            enhanceBtn.disabled = false;
        }
    });

    function updateImage(imagePath) {
        // Force a cache bust to ensure the new image loads
        const timestamp = new Date().getTime();
        // Construct absolute URL. Backend might return relative path like "static/gem_3_arch.png"
        // We need to make sure we don't double up on "static" if it's already there
        // But based on previous code, it seems we just append to base url.
        // Let's just use the filename if it's returned as a path

        // Clean up path if needed (remove leading slash)
        const cleanPath = imagePath.startsWith('/') ? imagePath.slice(1) : imagePath;

        archImage.src = `${API_BASE_URL}/${cleanPath}?t=${timestamp}`;

        archImage.onload = () => {
            // Image loaded
        };

        archImage.onerror = () => {
            showError('Failed to load the diagram image');
        };
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }
});
