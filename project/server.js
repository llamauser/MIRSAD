const path = require("path");
const http = require("http");
const express = require("express");
const { WebSocketServer } = require("ws");
const chokidar = require("chokidar");
const { spawn } = require("child_process");
const fs = require("fs");

// In-memory database (no MongoDB required)
const db = require('./database/inMemoryDB');

// Warehouse routes
const productRoutes = require('./routes/productRoutes');
const scanRoutes = require('./routes/scanRoutes');
const orderRoutes = require('./routes/orderRoutes');
const analyticsRoutes = require('./routes/analyticsRoutes');

// Basic configuration for paths and port.
const PORT = 3000;
const PROJECT_ROOT = __dirname;
const MODEL_DIR = path.join(PROJECT_ROOT, "AI_Model");  // Use local AI_Model folder
const PYTHON_SCRIPT = path.join(MODEL_DIR, "model_server.py");
const UPLOADS_DIR = path.join(PROJECT_ROOT, "uploads");

// Ensure uploads directory exists.
if (!fs.existsSync(UPLOADS_DIR)) {
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

// Serve the static HTML from the project root.
const app = express();
app.use(express.json());
app.use(express.static(PROJECT_ROOT));

// Create HTTP + WebSocket servers on the same port.
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

console.log('✓ Using in-memory database (no MongoDB required)');

// Track the Python child process and in-flight requests.
let pythonProc = null;
let isModelReady = false;
const pending = new Map();
let requestCounter = 0;

function startPython() {
  // Restart the Python process so it reloads the latest model.
  stopPython();

  isModelReady = false;
  // Use the venv Python interpreter
  const pythonPath = path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe");
  pythonProc = spawn(pythonPath, [PYTHON_SCRIPT, MODEL_DIR], {
    cwd: PROJECT_ROOT,
    stdio: ["pipe", "pipe", "pipe"],
  });

  pythonProc.stdout.setEncoding("utf-8");
  pythonProc.stderr.setEncoding("utf-8");

  // Parse JSON lines from Python and broadcast to clients.
  pythonProc.stdout.on("data", (chunk) => {
    const lines = chunk.split("\n").filter(Boolean);
    for (const line of lines) {
      let payload;
      try {
        payload = JSON.parse(line);
      } catch (err) {
        console.error("Invalid JSON from Python:", line);
        continue;
      }

      if (payload.type === "ready") {
        isModelReady = true;
        broadcast({ type: "status", message: payload.message || "Model ready." });
        continue;
      }

      if (payload.type === "error") {
        broadcast({ type: "error", message: payload.message || "Model error." });
        continue;
      }

      if (payload.type === "response") {
        const { id, message } = payload;
        pending.delete(id);
        broadcast({ type: "response", id, message });
        
        // Extract sensor data and broadcast to UE5
        try {
          const result = JSON.parse(message);
          
          // Log all raw model values
          console.log(`\n[MODEL OUTPUT] Request ID: ${id}`);
          console.log(`  Prediction: ${result.prediction}`);
          console.log(`  Confidence: ${result.confidence || 'N/A'}`);
          console.log(`  Probabilities: ${JSON.stringify(result.probabilities || [])}`);
          console.log(`  Classes: ${JSON.stringify(result.classes || [])}`);
          console.log(`  Features: ${result.num_features || 'N/A'}`);
          console.log(`  RMS Energy: ${result.rms_energy || 'N/A'}`);
          console.log(`  Max Amplitude: ${result.max_amplitude || 'N/A'}`);
          if (result.was_overridden) {
            console.log(`  ⚠️  OVERRIDDEN: Low volume detected - original prediction was ${result.original_prediction}`);
          }
          console.log('');
          
          console.log(`[DEBUG] Checking for sensor_${id} in pending map...`);
          console.log(`[DEBUG] pending.has('sensor_${id}'): ${pending.has(`sensor_${id}`)}`);
          console.log(`[DEBUG] Pending map keys:`, Array.from(pending.keys()));
          
          if (result.prediction !== undefined && pending.has(`sensor_${id}`)) {
            const sensorId = pending.get(`sensor_${id}`);
            console.log(`[BROADCAST] Sending sensor update: ${sensorId} -> Prediction: ${result.prediction}, Confidence: ${result.confidence || 0}`);
            broadcastSensorUpdate(sensorId, result.prediction, result.confidence || 0);
            pending.delete(`sensor_${id}`);
          } else {
            console.log(`[DEBUG] NOT broadcasting - prediction:${result.prediction}, has_sensor:${pending.has(`sensor_${id}`)}`);
          }
        } catch (e) {
          // Not JSON or no sensor ID
        }
      }
    }
  });

  // Surface Python stderr for debugging.
  pythonProc.stderr.on("data", (chunk) => {
    console.error("Python stderr:", chunk.trim());
  });

  // Mark the model unavailable if the process exits.
  pythonProc.on("exit", (code) => {
    isModelReady = false;
    console.log("Python process exited:", code);
  });
}

function stopPython() {
  // Gracefully stop the existing Python process.
  if (pythonProc) {
    pythonProc.kill();
    pythonProc = null;
  }
}

function sendToPython(audioPath) {
  // Forward the audio file path to the model process for inference.
  if (!pythonProc || !isModelReady) {
    broadcast({ type: "error", message: "Model is not ready yet." });
    return null;
  }

  const id = ++requestCounter;
  pending.set(id, true);
  const payload = JSON.stringify({ id, audioPath });
  pythonProc.stdin.write(payload + "\n");
  return id;
}

function broadcast(payload) {
  // Send a message to all connected clients (web UI + UE5).
  const message = JSON.stringify(payload);
  for (const client of wss.clients) {
    if (client.readyState === client.OPEN) {
      client.send(message);
    }
  }
}

function broadcastSensorUpdate(sensorId, prediction, confidence) {
  // Send sensor update to all WebSocket clients including UE5
  const message = {
    type: "sensor_update",
    sensorId: sensorId,
    prediction: prediction,
    confidence: confidence,
    timestamp: Date.now()
  };
  console.log(`[WS BROADCAST] Sending to ${wss.clients.size} clients:`, JSON.stringify(message));
  broadcast(message);
}

// Handle WebSocket connections from the browser.
wss.on("connection", (socket) => {
  socket.send(JSON.stringify({ type: "status", message: "Connected to server." }));
  
  // Broadcast a reset signal to ALL clients when a new connection is made
  // This ensures UE5 clears old sensor data when the web page refreshes
  broadcast({
    type: "reset_sensors",
    message: "New client connected - resetting all sensors",
    timestamp: Date.now()
  });

  socket.on("message", (data) => {
    let payload;
    try {
      payload = JSON.parse(data.toString());
    } catch (err) {
      socket.send(JSON.stringify({ type: "error", message: "Invalid message." }));
      return;
    }

    if (payload.type === "audio") {
      // Receive audio file data, save it temporarily, and send to Python.
      const timestamp = Date.now();
      const sensorId = payload.sensorId; // Track which sensor this is for
      const isStreaming = payload.isStreaming || false;
      
      // For streaming (live monitoring), use sensor-specific filenames and overwrite
      const filename = isStreaming 
        ? `${sensorId}_live.webm` 
        : `${timestamp}-${payload.filename || "audio.wav"}`;
      
      const audioPath = path.join(UPLOADS_DIR, filename);
      const buffer = Buffer.from(payload.data);
      
      fs.writeFile(audioPath, buffer, (err) => {
        if (err) {
          socket.send(JSON.stringify({ type: "error", message: "Failed to save audio file." }));
          return;
        }
        
        console.log(`[Upload] Saved ${filename} (${buffer.length} bytes) for ${sensorId}`);
        
        // For streaming webm files, convert to WAV first
        if (isStreaming && filename.endsWith('.webm')) {
          const wavPath = path.join(UPLOADS_DIR, `${sensorId}_live.wav`);
          
          // Use ffmpeg to convert webm to wav
          const { spawn } = require('child_process');
          // Try to find ffmpeg in common locations
          const ffmpegPath = process.platform === 'win32' 
            ? 'C:\\Users\\rima\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-8.0.1-essentials_build\\bin\\ffmpeg.exe'
            : 'ffmpeg';
          
          const ffmpeg = spawn(ffmpegPath, [
            '-y', // Overwrite output file
            '-i', audioPath,
            '-ar', '22050', // Sample rate for model
            '-ac', '1', // Mono
            '-f', 'wav',
            wavPath
          ]);
          
          ffmpeg.stderr.on('data', (data) => {
            // Optional: log ffmpeg output for debugging
            // console.log(`[FFmpeg] ${data}`);
          });
          
          ffmpeg.on('close', (code) => {
            if (code !== 0) {
              console.error(`[FFmpeg] Conversion failed for ${sensorId} (code ${code})`);
              return;
            }
            
            console.log(`[FFmpeg] Converted ${filename} to WAV for ${sensorId}`);
            
            // Delete the webm file after conversion
            fs.unlink(audioPath, () => {});
            
            // Now analyze the WAV file
            const reqId = sendToPython(wavPath);
            if (sensorId && reqId) {
              pending.set(`sensor_${reqId}`, sensorId);
            }
          });
        } else {
          // Regular file upload or WAV file
          const reqId = sendToPython(audioPath);
          if (sensorId && reqId) {
            pending.set(`sensor_${reqId}`, sensorId);
          }
        }
      });
    }
  });
});

// HTTP API endpoint for external clients (UE5, scripts, etc.)
app.post("/api/analyze", express.raw({ type: 'application/octet-stream', limit: '50mb' }), (req, res) => {
  const timestamp = Date.now();
  const sensorId = req.query.sensorId || req.body.sensorId || "unknown";
  const filename = `${timestamp}-api-${sensorId}.wav`;
  const audioPath = path.join(UPLOADS_DIR, filename);
  
  fs.writeFile(audioPath, req.body, (err) => {
    if (err) {
      return res.status(500).json({ error: "Failed to save audio file" });
    }
    
    if (!pythonProc || !isModelReady) {
      return res.status(503).json({ error: "Model is not ready yet" });
    }
    
    const id = ++requestCounter;
    
    // Create a one-time callback for this request
    const responseHandler = (chunk) => {
      const lines = chunk.split("\n").filter(Boolean);
      for (const line of lines) {
        try {
          const payload = JSON.parse(line);
          if (payload.type === "response" && payload.id === id) {
            pending.delete(id);
            pythonProc.stdout.off("data", responseHandler);
            
            try {
              const result = JSON.parse(payload.message);
              // Broadcast to UE5 and web clients
              broadcastSensorUpdate(sensorId, result.prediction, result.confidence || 0);
              return res.json(result);
            } catch (e) {
              return res.json({ message: payload.message });
            }
          }
        } catch (e) {
          // Invalid JSON, ignore
        }
      }
    };
    
    pythonProc.stdout.on("data", responseHandler);
    
    pending.set(id, true);
    const payload = JSON.stringify({ id, audioPath });
    pythonProc.stdin.write(payload + "\n");
    
    // Timeout after 30 seconds
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id);
        pythonProc.stdout.off("data", responseHandler);
        res.status(504).json({ error: "Request timeout" });
      }
    }, 30000);
  });
});

// Warehouse API routes
app.use('/api/products', productRoutes);
app.use('/api/scan', scanRoutes);
app.use('/api/orders', orderRoutes);
app.use('/api/analytics', analyticsRoutes);

// Make broadcast function globally available for warehouse controllers
global.broadcast = broadcast;

// Watch the model folder and reload on any file change.
const watcher = chokidar.watch(MODEL_DIR, {
  ignoreInitial: true,
  persistent: true,
});

watcher.on("all", () => {
  broadcast({ type: "status", message: "Model files changed. Reloading..." });
  startPython();
});

// Start the server and initial model load.
server.listen(PORT, () => {
  console.log(`Server listening at http://localhost:${PORT}`);
  startPython();
});
