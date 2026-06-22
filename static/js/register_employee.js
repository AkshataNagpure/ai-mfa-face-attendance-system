document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('registerEmployeeForm');
    const fileInput = document.getElementById('face_images');
    const startCaptureBtn = document.getElementById('startCaptureBtn');
    const clearButton = document.getElementById('clearCapturesBtn');
    const capturedPreview = document.getElementById('capturedPreview');
    const capturedImagesInput = document.getElementById('capturedImagesInput');
    const video = document.getElementById('cameraStream');
    const canvas = document.getElementById('captureCanvas');
    const meshCanvas = document.getElementById('faceMeshCanvas');
    const meshCtx = meshCanvas.getContext('2d');
    const progressBar = document.getElementById('captureProgressBar');
    const countText = document.getElementById('captureCountText');
    const passwordInput = document.getElementById('password');
    const passwordMessage = document.getElementById('passwordMessage');
    const togglePasswordBtn = document.getElementById('togglePassword');
    const eyeIcon = document.getElementById('eyeIcon');
    const eyeOffIcon = document.getElementById('eyeOffIcon');
    const emailInput = document.getElementById('email');
    const emailMessage = document.getElementById('emailMessage');

    let capturedImages = [];
    let isCapturing = false;
    let faceMesh = null;
    const MAX_CAPTURES = 20;

    // Initialize MediaPipe Face Mesh
    function initFaceMesh() {
        faceMesh = new FaceMesh({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
            }
        });

        faceMesh.setOptions({
            maxNumFaces: 1,
            refineLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5
        });

        faceMesh.onResults(onResults);

        const camera = new Camera(video, {
            onFrame: async () => {
                await faceMesh.send({ image: video });
            },
            width: 640,
            height: 480
        });
        camera.start();
    }

    function onResults(results) {
        // Resize canvas to match video
        if (meshCanvas.width !== video.videoWidth || meshCanvas.height !== video.videoHeight) {
            meshCanvas.width = video.videoWidth;
            meshCanvas.height = video.videoHeight;
        }

        meshCtx.save();
        meshCtx.clearRect(0, 0, meshCanvas.width, meshCanvas.height);

        if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
            const landmarks = results.multiFaceLandmarks[0];

            // Draw face mesh edges
            drawConnectors(meshCtx, landmarks, FACEMESH_TESSELATION, { color: '#C0C0C070', lineWidth: 1 });
            drawConnectors(meshCtx, landmarks, FACEMESH_RIGHT_EYE, { color: '#FF3030' });
            drawConnectors(meshCtx, landmarks, FACEMESH_RIGHT_EYEBROW, { color: '#FF3030' });
            drawConnectors(meshCtx, landmarks, FACEMESH_LEFT_EYE, { color: '#30FF30' });
            drawConnectors(meshCtx, landmarks, FACEMESH_LEFT_EYEBROW, { color: '#30FF30' });
            drawConnectors(meshCtx, landmarks, FACEMESH_FACE_OVAL, { color: '#E0E0E0' });
            drawConnectors(meshCtx, landmarks, FACEMESH_LIPS, { color: '#E0E0E0' });

            // Highlight the "face triangle" (nose, eyes)
            const noseTip = landmarks[1];
            const leftEye = landmarks[33];
            const rightEye = landmarks[263];

            meshCtx.beginPath();
            meshCtx.moveTo(noseTip.x * meshCanvas.width, noseTip.y * meshCanvas.height);
            meshCtx.lineTo(leftEye.x * meshCanvas.width, leftEye.y * meshCanvas.height);
            meshCtx.lineTo(rightEye.x * meshCanvas.width, rightEye.y * meshCanvas.height);
            meshCtx.closePath();
            meshCtx.strokeStyle = '#3498db';
            meshCtx.lineWidth = 3;
            meshCtx.stroke();

            // Add a subtle fill to the triangle
            meshCtx.fillStyle = 'rgba(52, 152, 219, 0.2)';
            meshCtx.fill();

            if (isCapturing && capturedImages.length < MAX_CAPTURES) {
                captureFrame();
            }
        }
        meshCtx.restore();
    }

    function captureFrame() {
        if (capturedImages.length >= MAX_CAPTURES) {
            stopAutoCapture();
            return;
        }

        const context = canvas.getContext('2d');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8);

        capturedImages.push(dataUrl);
        updateProgress();

        if (capturedImages.length % 5 === 0) {
            updateCapturedPreview();
        }
    }

    function updateProgress() {
        const percent = (capturedImages.length / MAX_CAPTURES) * 100;
        progressBar.style.width = `${percent}%`;
        countText.textContent = `${capturedImages.length}/${MAX_CAPTURES} Captured`;

        if (capturedImages.length >= MAX_CAPTURES) {
            stopAutoCapture();
            persistCapturedImages();
            countText.textContent = "Done! 20/20 Captured";
            progressBar.style.background = "#2ecc71";
        }
    }

    function stopAutoCapture() {
        isCapturing = false;
        startCaptureBtn.textContent = "Start Auto Capture";
        startCaptureBtn.disabled = false;
    }

    function updateCapturedPreview() {
        capturedPreview.innerHTML = '';
        const displayLimit = 5; // Just show a few for preview

        const text = document.createElement('p');
        text.textContent = `Latest captures (${capturedImages.length} total):`;
        text.style.fontSize = "12px";
        text.style.margin = "5px 0";
        capturedPreview.appendChild(text);

        const grid = document.createElement('div');
        grid.className = 'capture-grid';
        grid.style.display = 'flex';
        grid.style.gap = '5px';
        grid.style.overflowX = 'auto';

        capturedImages.slice(-displayLimit).forEach((imageData, index) => {
            const img = document.createElement('img');
            img.src = imageData;
            img.style.width = '60px';
            img.style.height = '60px';
            img.style.objectFit = 'cover';
            img.style.borderRadius = '4px';
            grid.appendChild(img);
        });
        capturedPreview.appendChild(grid);
    }

    function persistCapturedImages() {
        capturedImagesInput.value = JSON.stringify(capturedImages);
    }

    startCaptureBtn.addEventListener('click', () => {
        if (capturedImages.length >= MAX_CAPTURES) {
            capturedImages = [];
            updateProgress();
        }
        isCapturing = true;
        startCaptureBtn.textContent = "Capturing...";
        startCaptureBtn.disabled = true;
    });

    clearButton.addEventListener('click', () => {
        capturedImages = [];
        isCapturing = false;
        persistCapturedImages();
        updateProgress();
        capturedPreview.innerHTML = '';
        progressBar.style.background = "#3498db";
    });

    function validatePassword(password) {
        const rules = [
            { check: p => p.length >= 8, msg: "Minimum 8 characters length" },
            { check: p => /[A-Z]/.test(p), msg: "At least one uppercase letter (A–Z)" },
            { check: p => /[a-z]/.test(p), msg: "At least one lowercase letter (a–z)" },
            { check: p => /[0-9]/.test(p), msg: "At least one digit (0–9)" },
            { check: p => /[@#$%^&*!]/.test(p), msg: "At least one special character from: @ # $ % ^ & * !" },
            { check: p => !/\s/.test(p), msg: "No spaces allowed" }
        ];

        let failedRules = [];
        for (const rule of rules) {
            if (!rule.check(password)) {
                failedRules.push(rule.msg);
            }
        }
        return failedRules;
    }

    if (passwordInput && passwordMessage) {
        passwordInput.addEventListener('input', () => {
            const password = passwordInput.value;
            if (!password) {
                passwordMessage.style.display = 'none';
                return;
            }

            const failedRules = validatePassword(password);
            passwordMessage.style.display = 'block';

            if (failedRules.length > 0) {
                passwordMessage.style.color = '#e74c3c';
                passwordMessage.innerHTML = 'Invalid password:<br>• ' + failedRules.join('<br>• ');
            } else {
                passwordMessage.style.color = '#2ecc71';
                passwordMessage.innerHTML = 'Password is strong and valid.';
            }
        });
    }

    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', () => {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                eyeIcon.style.display = 'none';
                eyeOffIcon.style.display = 'inline';
                togglePasswordBtn.style.color = 'var(--primary-color, #6366f1)';
            } else {
                passwordInput.type = 'password';
                eyeIcon.style.display = 'inline';
                eyeOffIcon.style.display = 'none';
                togglePasswordBtn.style.color = 'var(--text-secondary, #94a3b8)';
            }
        });
    }

    function validateEmail(email) {
        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        return emailRegex.test(email);
    }

    if (emailInput && emailMessage) {
        emailInput.addEventListener('input', () => {
            const email = emailInput.value.trim();
            if (!email) {
                emailMessage.style.display = 'none';
                return;
            }

            emailMessage.style.display = 'block';
            if (validateEmail(email)) {
                emailMessage.style.color = '#2ecc71';
                emailMessage.textContent = 'Email address is valid.';
            } else {
                emailMessage.style.color = '#e74c3c';
                emailMessage.textContent = 'Please enter a valid email address.';
            }
        });
    }

    const mobileInputEl = document.getElementById('mobile');
    const mobileMessageEl = document.getElementById('mobileMessage');
    if (mobileInputEl && mobileMessageEl) {
        mobileInputEl.addEventListener('input', () => {
            const val = mobileInputEl.value.trim();
            if (!val) {
                mobileMessageEl.style.display = 'none';
                return;
            }
            if (val.length !== 10 || !/^\d{10}$/.test(val)) {
                mobileMessageEl.style.display = 'block';
                mobileMessageEl.style.color = '#e74c3c';
                mobileMessageEl.textContent = 'plz enter valid number (must be exactly 10 digits)';
            } else {
                mobileMessageEl.style.display = 'block';
                mobileMessageEl.style.color = '#2ecc71';
                mobileMessageEl.textContent = 'Valid mobile number.';
            }
        });
    }

    form.addEventListener('submit', (event) => {
        if (emailInput) {
            const email = emailInput.value.trim();
            if (!validateEmail(email)) {
                event.preventDefault();
                alert("Please enter a valid email address.");
                emailInput.focus();
                return;
            }
        }

        const mobileInput = document.getElementById('mobile');
        if (mobileInput) {
            const mobileValue = mobileInput.value.trim();
            if (mobileValue !== "") {
                if (mobileValue.length !== 10 || !/^\d{10}$/.test(mobileValue)) {
                    event.preventDefault();
                    alert("plz enter valid number (must be exactly 10 digits)");
                    mobileInput.focus();
                    return;
                }
            }
        }

        if (passwordInput) {
            const password = passwordInput.value;
            const failedRules = validatePassword(password);
            if (failedRules.length > 0) {
                event.preventDefault();
                alert("Please fix the password errors before submitting.");
                return;
            }
        }
        const uploadCount = fileInput.files ? fileInput.files.length : 0;
        const captureCount = capturedImages.length;

        if (captureCount < MAX_CAPTURES) {
            event.preventDefault();
            alert(`Please capture all ${MAX_CAPTURES} face images for training.`);
            return;
        }

        persistCapturedImages();
    });

    // Start Face Mesh
    initFaceMesh();
});
