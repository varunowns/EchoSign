'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import Header from '@/components/echosign/Header';
import WebcamStudio from '@/components/echosign/WebcamStudio';
import NeuralEngine from '@/components/echosign/NeuralEngine';
import TranscriptDock from '@/components/echosign/TranscriptDock';
import { useBackendInference } from '@/hooks/useBackendInference';

const CAPTURE_INTERVAL_MS = 33; // 30 FPS to match backend capability

const GESTURE_SENTENCES: Record<string, string> = {
  A: 'The letter A',
  B: 'The letter B',
  C: 'The letter C',
  D: 'The letter D',
  E: 'The letter E',
  F: 'The letter F',
  G: 'The letter G',
  H: 'The letter H',
  I: 'The letter I',
  J: 'The letter J',
  K: 'The letter K',
  L: 'The letter L',
  M: 'The letter M',
  N: 'The letter N',
  O: 'The letter O',
  P: 'The letter P',
  Q: 'The letter Q',
  R: 'The letter R',
  S: 'The letter S',
  T: 'The letter T',
};

interface TranscriptEntry {
  id: number;
  text: string;
  timestamp: string;
  gesture: string;
}

function getTimestamp(): string {
  return new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export default function EchoSignDashboard() {
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [gesture, setGesture] = useState<string>('WAITING');
  const [confidence, setConfidence] = useState(0);
  const [debounceProgress, setDebounceProgress] = useState(0);
  const [isPulsing, setIsPulsing] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraStatus, setCameraStatus] = useState('Camera idle');

  const { status, lastMessage, connect, disconnect, sendFrame, checkHealth } = useBackendInference();

  const predictionStabilityRef = useRef<{pred: string, count: number, lastCommitted: string | null}>({pred: '', count: 0, lastCommitted: null});
  const entryIdRef = useRef(0);
  const debounceAnimRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const debounceResetRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const captureIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearGestureAnimation = useCallback(() => {
    if (debounceAnimRef.current) {
      clearInterval(debounceAnimRef.current);
      debounceAnimRef.current = null;
    }
    if (debounceResetRef.current) {
      clearTimeout(debounceResetRef.current);
      debounceResetRef.current = null;
    }
  }, []);

  const commitLetter = useCallback(
    (letter: string, conf: number) => {
      // Commit to transcript immediately — do NOT wait for animation.
      const entry: TranscriptEntry = {
        id: ++entryIdRef.current,
        text: GESTURE_SENTENCES[letter] || letter,
        timestamp: getTimestamp(),
        gesture: letter,
      };
      setTranscript((prev) => [...prev, entry]);

      // Voice (fire once, not on every repeat)
      if (isVoiceActive) {
        setIsSpeaking(true);
        setTimeout(() => setIsSpeaking(false), 2000);
      }
    },
    [isVoiceActive]
  );

  const triggerGestureTransition = useCallback(
    (newGesture: string, newConfidence: number) => {
      setGesture(newGesture);
      setConfidence(newConfidence);
      setIsPulsing(true);
      setDebounceProgress(0);

      clearGestureAnimation();

      // Animate the debounce bar over 300 ms (purely visual).
      const startTime = Date.now();
      const duration = 300;
      debounceAnimRef.current = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        setDebounceProgress(progress);
        if (progress >= 1) {
          clearGestureAnimation();
          debounceResetRef.current = setTimeout(() => {
            setIsPulsing(false);
            setDebounceProgress(0);
          }, 400);
        }
      }, 16);
    },
    [clearGestureAnimation]
  );

  const stopCaptureLoop = useCallback(() => {
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }
  }, []);

  const stopCamera = useCallback(() => {
    stopCaptureLoop();
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraReady(false);
    setCameraStatus('Camera idle');
  }, [stopCaptureLoop]);

  const startCamera = useCallback(async () => {
    if (mediaStreamRef.current) {
      setCameraReady(true);
      return true;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError('Your browser does not support webcam access.');
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user',
        },
      });

      mediaStreamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        video.muted = true;
        await video.play().catch(() => undefined);
      }
      setCameraError(null);
      setCameraReady(true);
      setCameraStatus('Webcam connected');
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to access webcam.';
      setCameraError(message);
      setCameraStatus('Camera blocked');
      return false;
    }
  }, []);

  const handleToggleLiveMode = useCallback(async () => {
    if (isLiveMode) {
      setIsLiveMode(false);
      disconnect();
      stopCamera();
      clearGestureAnimation();
      setIsPulsing(false);
      setDebounceProgress(0);
      setGesture('WAITING');
      setConfidence(0);
      setFps(0);
      setLatency(0);
      return;
    }

    setCameraStatus('Starting webcam');
    const cameraStarted = await startCamera();
    if (!cameraStarted) {
      return;
    }

    setCameraStatus('Checking backend');
    const healthy = await checkHealth();
    if (!healthy) {
      setCameraError('Backend is not reachable at localhost:8000.');
      stopCamera();
      return;
    }

    setCameraStatus('Connecting to live inference');
    setCameraError(null);
    connect();
    setIsLiveMode(true);
  }, [checkHealth, clearGestureAnimation, connect, disconnect, isLiveMode, startCamera, stopCamera]);

  useEffect(() => {
    if (!isLiveMode || !lastMessage) return;

    if (typeof lastMessage.fps === 'number') {
      setFps(lastMessage.fps);
    }
    if (typeof lastMessage.latency_ms === 'number') {
      setLatency(lastMessage.latency_ms);
    }

    if (lastMessage.error) {
      setCameraError(lastMessage.error);
    }

    if (lastMessage.message) {
      setCameraStatus(lastMessage.message);
    }

    if (lastMessage.prediction && typeof lastMessage.confidence === 'number') {
      const pred = lastMessage.prediction;
      const conf = lastMessage.confidence;
      const displayConfidence = conf <= 1 ? conf * 100 : conf;

      // Stability check: only act when same prediction persists
      // for 3+ frames (prevents flickering from oscillating model output).
      // The backend PostProcessor already gates commits via cooldown, but we
      // add a second layer here so the UI does not flicker mid-gesture.
      const stab = predictionStabilityRef.current;
      if (pred === stab.pred) {
        stab.count++;
      } else {
        stab.pred = pred;
        stab.count = 1;
      }

      if (stab.count >= 3) {
        // Commit the letter to transcript immediately (the animation below
        // is purely visual).  Only commit when it differs from the last
        // committed prediction so we do not flood the transcript with
        // repeated entries for the same held sign.
        if (pred !== stab.lastCommitted) {
          stab.lastCommitted = pred;
          commitLetter(pred, displayConfidence);
        }
        // Start the pulsing / progress-bar animation on every 3-frame
        // batch so the UI stays alive even for a held sign.
        triggerGestureTransition(pred, displayConfidence);
      }
    }
  }, [isLiveMode, lastMessage, triggerGestureTransition, commitLetter]);

  const captureFrame = useCallback(() => {
    if (!isLiveMode || !cameraReady || !status.connected) return;

    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;

    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) return;

    // Downscale to a reasonable size for WebSocket transmission
    // Smaller frames keep PNG sizes manageable while preserving detail for MediaPipe
    const MAX_CAPTURE_WIDTH = 480;
    const scale = Math.min(1, MAX_CAPTURE_WIDTH / width);
    const captureWidth = Math.round(width * scale);
    const captureHeight = Math.round(height * scale);

    canvas.width = captureWidth;
    canvas.height = captureHeight;

    const context = canvas.getContext('2d');
    if (!context) return;

    // Mirror the capture so the backend sees the same orientation as the user preview.
    context.save();
    context.scale(-1, 1);
    context.drawImage(video, -captureWidth, 0, captureWidth, captureHeight);
    context.restore();

    // Use PNG for lossless quality (larger but preserves detail for MediaPipe)
    // Downscaling to 480px wide keeps PNG sizes ~50-150KB per frame
    const frameBase64 = canvas.toDataURL('image/png').split(',')[1];
    const sent = sendFrame(frameBase64);

    if (!sent) {
      console.warn('[WARN] Frame not sent - WebSocket not open');
    }
  }, [cameraReady, isLiveMode, sendFrame, status.connected]);

  useEffect(() => {
    if (!isLiveMode || !cameraReady || !status.connected) {
      stopCaptureLoop();
      return;
    }

    captureIntervalRef.current = setInterval(captureFrame, CAPTURE_INTERVAL_MS);
    return () => {
      stopCaptureLoop();
    };
  }, [cameraReady, captureFrame, isLiveMode, status.connected, stopCaptureLoop]);

  useEffect(() => {
    if (isVoiceActive && transcript.length > 0) {
      setIsSpeaking(true);
      const t = setTimeout(() => setIsSpeaking(false), 2200);
      return () => clearTimeout(t);
    }
  }, [transcript.length, isVoiceActive]);

  useEffect(() => {
    if (!isLiveMode) return;

    if (status.connected) {
      setCameraStatus('Live inference running');
    } else if (status.error) {
      setCameraStatus('Waiting for backend');
    }
  }, [isLiveMode, status.connected, status.error]);

  useEffect(() => {
    return () => {
      disconnect();
      stopCamera();
      clearGestureAnimation();
    };
  }, [clearGestureAnimation, disconnect, stopCamera]);

  const handleClearTranscript = () => {
    setTranscript([]);
    entryIdRef.current = 0;
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background:
          'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,242,254,0.04) 0%, transparent 60%), #0B0F19',
      }}
    >
      <Header
        isLiveMode={isLiveMode}
        isBackendConnected={status.connected}
        onToggleLiveMode={handleToggleLiveMode}
      />

      <main className="flex-1 p-4 md:p-6 flex flex-col gap-4">
        <canvas ref={captureCanvasRef} className="hidden" />

        {isLiveMode && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="flex items-center gap-3 px-4 py-2 rounded-lg border border-cyan-500/30 bg-cyan-500/5"
          >
            <motion.div
              className="w-2 h-2 rounded-full bg-cyan-400"
              animate={{ opacity: [1, 0.2, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
            />
            <span className="text-xs font-mono-custom text-cyan-300">
              LIVE TRANSLATION ACTIVE - Webcam frames are streaming to the backend in real time.
            </span>
            <span className="ml-auto font-mono-custom text-[10px] text-cyan-400/60">
              {status.connected ? 'Socket connected' : 'Connecting...'}
            </span>
          </motion.div>
        )}

        {cameraError && (
          <div className="px-4 py-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-200">
            {cameraError}
          </div>
        )}

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-7 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-md p-4 flex flex-col">
            <WebcamStudio
              isActive={isLiveMode}
              gesture={gesture}
              fps={fps}
              latency={latency}
              videoRef={videoRef}
              cameraReady={cameraReady}
              backendConnected={status.connected}
              cameraStatus={cameraStatus}
            />
          </div>

          <div className="lg:col-span-5 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-md p-4 overflow-hidden">
            <NeuralEngine
              isActive={isLiveMode}
              isPulsing={isPulsing}
              gesture={gesture}
              confidence={confidence}
              debounceProgress={debounceProgress}
              modelMetrics={{
                accuracy: '98.7%',
                latency: latency > 0 ? `${latency}ms` : '---',
                inferenceHz: fps > 0 ? Math.round(fps) : 0,
              }}
            />
          </div>
        </div>

        <TranscriptDock
          transcript={transcript}
          onClear={handleClearTranscript}
          isVoiceActive={isVoiceActive}
          onVoiceToggle={() => setIsVoiceActive((v) => !v)}
          isSpeaking={isSpeaking}
        />
      </main>

      {/* Footer */}
      <footer className="px-6 py-2 border-t border-cyan-500/10 flex items-center justify-between">
        <span className="font-mono-custom text-[9px] text-slate-600">
          EchoSign M6 — Neural ASL Translation Engine &copy; 2024
        </span>
        <div className="flex items-center gap-3">
          {['FastAPI', 'MediaPipe', 'WebSocket', 'ASL2024'].map((tech) => (
            <span
              key={tech}
              className="font-mono-custom text-[9px] text-slate-600 px-1.5 py-0.5 rounded bg-slate-800/60 border border-slate-700/30"
            >
              {tech}
            </span>
          ))}
        </div>
      </footer>
    </div>
  );
}
