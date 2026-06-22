let currentStream = null;
let currentAction = '';
let faceMesh = null;
let cameraHelper = null;

function openAttendanceOptionsModal() {
    document.getElementById('attendanceOptionsModal').style.display = 'block';
    // Warm up TTS engine on first user interaction
    if ('speechSynthesis' in window) {
        const silent = new SpeechSynthesisUtterance("");
        silent.volume = 0;
        window.speechSynthesis.speak(silent);
    }
}

function closeAttendanceOptionsModal() {
    document.getElementById('attendanceOptionsModal').style.display = 'none';
}

function speakText(text) {
    console.log("Attempting to speak:", text);
    if ('speechSynthesis' in window) {
        // Cancel any ongoing speech
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);

        // Try to find a good English voice
        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0) {
            utterance.voice = voices.find(v => v.lang.includes('en')) || voices[0];
        }

        utterance.rate = 0.9;
        utterance.pitch = 1;
        utterance.volume = 1;

        utterance.onerror = (event) => {
            console.error("SpeechSynthesisUtterance error:", event.error);
        };

        window.speechSynthesis.speak(utterance);
    } else {
        console.warn("Speech synthesis not supported in this browser.");
    }
}

function openCameraModal(action) {
    currentAction = action;
    closeAttendanceOptionsModal();

    const modal = document.getElementById('cameraModal');
    const title = document.getElementById('modalTitle');

    let titleText = 'Attendance Action';
    switch (action) {
        case 'in': titleText = 'Mark In'; break;
        case 'break_out': titleText = 'Break Out'; break;
        case 'break_in': titleText = 'Break In'; break;
        case 'out': titleText = 'Mark Out'; break;
    }
    title.textContent = titleText;

    modal.style.display = 'block';
    startCamera();
}

function closeCameraModal() {
    const modal = document.getElementById('cameraModal');
    modal.style.display = 'none';
    stopCamera();
    if (faceMesh) {
        faceMesh.close();
        faceMesh = null;
    }
    if (cameraHelper) {
        cameraHelper.stop();
        cameraHelper = null;
    }
    document.getElementById('attendanceResult').innerHTML = '';
    document.getElementById('attendanceEmotion').innerHTML = '';
}

function startCamera() {
    const video = document.getElementById('attendanceVideo');
    const meshCanvas = document.getElementById('faceMeshCanvas');
    const meshCtx = meshCanvas.getContext('2d');

    // Initialize MediaPipe Face Mesh
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

    faceMesh.onResults((results) => {
        // Resize canvas to match video
        if (meshCanvas.width !== video.videoWidth || meshCanvas.height !== video.videoHeight) {
            meshCanvas.width = video.videoWidth;
            meshCanvas.height = video.videoHeight;
        }

        meshCtx.save();
        meshCtx.clearRect(0, 0, meshCanvas.width, meshCanvas.height);

        if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
            const landmarks = results.multiFaceLandmarks[0];

            // Draw face mesh edges (Tesselation)
            drawConnectors(meshCtx, landmarks, FACEMESH_TESSELATION, { color: '#C0C0C070', lineWidth: 1 });

            // Draw feature highlights
            drawConnectors(meshCtx, landmarks, FACEMESH_RIGHT_EYE, { color: '#FF3030' });
            drawConnectors(meshCtx, landmarks, FACEMESH_LEFT_EYE, { color: '#30FF30' });
            drawConnectors(meshCtx, landmarks, FACEMESH_FACE_OVAL, { color: '#E0E0E0' });

            // Highlight the "Face Triangle" for feature detection
            const noseTip = landmarks[1];
            const leftEye = landmarks[33];
            const rightEye = landmarks[263];

            meshCtx.beginPath();
            meshCtx.moveTo(noseTip.x * meshCanvas.width, noseTip.y * meshCanvas.height);
            meshCtx.lineTo(leftEye.x * meshCanvas.width, leftEye.y * meshCanvas.height);
            meshCtx.lineTo(rightEye.x * meshCanvas.width, rightEye.y * meshCanvas.height);
            meshCtx.closePath();
            meshCtx.strokeStyle = '#3498db';
            meshCtx.lineWidth = 3; // Thicker for visibility
            meshCtx.stroke();

            // Add a subtle fill to the triangle
            meshCtx.fillStyle = 'rgba(52, 152, 219, 0.2)';
            meshCtx.fill();
        }
        meshCtx.restore();
    });

    cameraHelper = new Camera(video, {
        onFrame: async () => {
            if (faceMesh) {
                await faceMesh.send({ image: video });
            }
        },
        width: 640,
        height: 480
    });
    cameraHelper.start();
}

function stopCamera() {
    const video = document.getElementById('attendanceVideo');
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
    }
    video.srcObject = null;
}

function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("Geolocation is not supported by your browser."));
        } else {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    });
                },
                (error) => {
                    let msg = "Unable to retrieve your location.";
                    switch (error.code) {
                        case error.PERMISSION_DENIED:
                            msg = "Location access denied. Please enable location permissions to mark attendance.";
                            break;
                        case error.POSITION_UNAVAILABLE:
                            msg = "Location information is unavailable.";
                            break;
                        case error.TIMEOUT:
                            msg = "The request to get your location timed out.";
                            break;
                    }
                    reject(new Error(msg));
                },
                {
                    enableHighAccuracy: true,
                    timeout: 30000,
                    maximumAge: 0
                }
            );
        }
    });
}

function captureAndProcess() {
    const video = document.getElementById('attendanceVideo');
    const canvas = document.getElementById('attendanceCanvas');
    const resultDiv = document.getElementById('attendanceResult');
    const captureBtn = document.getElementById('captureBtn');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    const imageData = canvas.toDataURL('image/jpeg');

    resultDiv.innerHTML = '<p>Acquiring location...</p>';
    captureBtn.disabled = true;

    getCurrentLocation()
        .then(location => {
            resultDiv.innerHTML = '<p>Processing...</p>';
            return fetch('/api/mark_attendance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image: imageData,
                    action: currentAction,
                    latitude: location.latitude,
                    longitude: location.longitude,
                    request_id: crypto.randomUUID()
                })
            });
        })
        .then(response => response.json())
        .then(data => {
            captureBtn.disabled = false;
            if (data.success) {
                speakText(`${data.message}. Emotion: ${data.emotion}. Time: ${data.time}.`);
                resultDiv.innerHTML = `
                <div class="success-status">
                    <p class="success-msg">${data.message}</p>
                    <div class="status-summary-label">Attendance Details:</div>
                    <div class="status-details">
                        <div class="status-item">
                            <span class="status-icon"></span>
                            <span class="status-text">Time: <strong>${data.time}</strong></span>
                        </div>
                        <div class="status-item">
                            <span class="status-icon"></span>
                            <span class="status-text">Emotion: <strong style="text-transform: capitalize;">${data.emotion}</strong></span>
                        </div>
                    </div>
                </div>
            `;
                setTimeout(() => {
                    closeCameraModal();
                }, 6000);
            } else {
                resultDiv.innerHTML = `<p class="error">${data.message}</p>`;
            }
        })
        .catch(error => {
            captureBtn.disabled = false;
            console.error('Error:', error);
            resultDiv.innerHTML = `<p class="error">${error.message}</p>`;
        });
}


// Close modal when clicking outside
window.onclick = function (event) {
    const cameraModal = document.getElementById('cameraModal');
    const optionsModal = document.getElementById('attendanceOptionsModal');

    if (event.target == cameraModal) {
        closeCameraModal();
    }
    if (event.target == optionsModal) {
        closeAttendanceOptionsModal();
    }
}

// Pre-load voices for TTS
document.addEventListener('DOMContentLoaded', () => {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices();
    }
});
