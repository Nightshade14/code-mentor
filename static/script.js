document.addEventListener('DOMContentLoaded', () => {
    const submitBtn = document.getElementById('submitBtn');
    const repoInput = document.getElementById('repoUrl');
    const resultSection = document.getElementById('result-section');
    const archImage = document.getElementById('archImage');
    const errorMessage = document.getElementById('error-message');

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

            // The backend returns the path to the image. 
            // We'll assume the backend serves it statically or we need to adjust the path.
            // For now, let's assume the backend returns a relative path we can use directly 
            // or we hardcode the expectation based on the user request "renders / opens the image 'gem_3_arch.png'"

            // Force a cache bust to ensure the new image loads
            const timestamp = new Date().getTime();
            // Use absolute URL for the image
            archImage.src = `${API_BASE_URL}/static/gem_3_arch.png?t=${timestamp}`;

            // Wait for image to load before showing
            archImage.onload = () => {
                resultSection.classList.remove('hidden');
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
            };

            archImage.onerror = () => {
                showError('Failed to load the generated diagram');
                submitBtn.classList.remove('loading');
                submitBtn.disabled = false;
            };

        } catch (error) {
            console.error('Error:', error);
            showError(error.message);
            submitBtn.classList.remove('loading');
            submitBtn.disabled = false;
        }
    });

    function showError(msg) {
        errorMessage.textContent = msg;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }
});
