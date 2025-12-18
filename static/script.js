document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const videoFile = document.getElementById('videoFile');
    const fileInfo = document.getElementById('fileInfo');
    const processBtn = document.getElementById('processBtn');
    const progressSection = document.getElementById('progressSection');
    const resultSection = document.getElementById('resultSection');
    const errorSection = document.getElementById('errorSection');
    const progressFill = document.getElementById('progressFill');
    
    // File selection feedback
    videoFile.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            fileInfo.textContent = `${file.name} (${sizeMB} MB)`;
        }
    });
    
    // Form submission
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Hide previous results
        resultSection.style.display = 'none';
        errorSection.style.display = 'none';
        
        // Show progress
        progressSection.style.display = 'block';
        processBtn.disabled = true;
        processBtn.textContent = 'Procesando...';
        
        // Prepare form data
        const formData = new FormData(uploadForm);
        
        // Simulate progress steps
        const steps = ['step1', 'step2', 'step3', 'step4'];
        let currentStep = 0;
        
        const updateProgress = () => {
            steps.forEach((step, index) => {
                const element = document.getElementById(step);
                if (index < currentStep) {
                    element.classList.add('completed');
                    element.classList.remove('active');
                } else if (index === currentStep) {
                    element.classList.add('active');
                    element.classList.remove('completed');
                } else {
                    element.classList.remove('active', 'completed');
                }
            });
            progressFill.style.width = `${(currentStep / steps.length) * 100}%`;
        };
        
        // Animate progress
        const progressInterval = setInterval(() => {
            if (currentStep < steps.length - 1) {
                currentStep++;
                updateProgress();
            }
        }, 2000);
        
        updateProgress();
        
        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            clearInterval(progressInterval);
            
            if (response.ok && data.success) {
                // Complete all steps
                currentStep = steps.length;
                updateProgress();
                progressFill.style.width = '100%';
                
                // Show results after a brief delay
                setTimeout(() => {
                    progressSection.style.display = 'none';
                    resultSection.style.display = 'block';
                    
                    // Set download links
                    document.getElementById('downloadSubtitle').href = 
                        `/download/${data.subtitle_file}`;
                    document.getElementById('downloadVideo').href = 
                        `/download/${data.output_video}`;
                    
                    // Reset form
                    uploadForm.reset();
                    fileInfo.textContent = '';
                    processBtn.disabled = false;
                    processBtn.textContent = 'Procesar Video';
                }, 1000);
            } else {
                throw new Error(data.error || 'Error procesando el video');
            }
        } catch (error) {
            clearInterval(progressInterval);
            progressSection.style.display = 'none';
            errorSection.style.display = 'block';
            document.getElementById('errorMessage').textContent = error.message;
            processBtn.disabled = false;
            processBtn.textContent = 'Procesar Video';
        }
    });
});



