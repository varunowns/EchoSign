'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import Header from '@/components/echosign/Header';
import WebcamStudio from '@/components/echosign/WebcamStudio';
import NeuralEngine from '@/components/echosign/NeuralEngine';
import TranscriptDock from '@/components/echosign/TranscriptDock';
import { useBackendInference } from '@/hooks/useBackendInference';

const GESTURES = ['HELLO', 'PLEASE', 'THANK YOU', 'YES', 'HELP'] as const;

const GESTURE_SENTENCES: Record<string, string> = {
  HELLO: 'Hello, how are you doing today?',
  PLEASE: 'Please help me with this.',
  'THANK YOU': 'Thank you so much for your assistance.',
  YES: 'Yes, I understand you.',
  HELP: 'I need some help right now.',
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
  const [currentGestureIdx, setCurrentGestureIdx] = useState(0);
  const [gesture, setGesture] = useState<string>('THANK YOU');
  const [confidence, setConfidence] = useState(96.4);
  const [debounceProgress, setDebounceProgress] = useState(0);
  const [isPulsing, setIsPulsing] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [fps, setFps] = useState(30.0);
  const [latency, setLatency] = useState(142);
  const [useDemo, setUseDemo] = useState(true);

  const { status, predictions, connect, disconnect } = useBackendInference();

  const entryIdRef = useRef(0);
  const debounceAnimRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const gestureIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const triggerGestureTransition = useCallback(
    (newGesture: string, newConfidence: number) => {
      setGesture(newGesture);
      setConfidence(newConfidence);
      setIsPulsing(true);
      setDebounceProgress(0);

      // Clear any existing debounce animation
      if (debounceAnimRef.current) clearInterval(debounceAnimRef.current);

      // Animate debounce ring over 300ms
      const startTime = Date.now();
      const duration = 300;
      debounceAnimRef.current = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        setDebounceProgress(progress);
        if (progress >= 1) {
          if (debounceAnimRef.current) clearInterval(debounceAnimRef.current);
          // Commit to transcript
          const entry: TranscriptEntry = {
            id: ++entryIdRef.current,
            text: GESTURE_SENTENCES[newGesture] || newGesture,
            timestamp: getTimestamp(),
            gesture: newGesture,
          };
          setTranscript((prev) => [...prev, entry]);

          // Trigger TTS simulation
          if (isVoiceActive) {
            setIsSpeaking(true);
            setTimeout(() => setIsSpeaking(false), 2000);
          }

          setTimeout(() => {
            setIsPulsing(false);
            setDebounceProgress(0);
          }, 400);
        }
      }, 16);
    },
    [isVoiceActive]
  );

  // Handle live mode toggle with backend connection
  const handleToggleLiveMode = useCallback(() => {
    setIsLiveMode((prev) => {
      const enable = !prev;
      if (enable && status.healthy && !useDemo) {
        connect();
      } else {
        setUseDemo(true);
        disconnect();
      }
      return enable;
    });
  }, [status.healthy, useDemo, connect, disconnect]);

  // Listen for real backend predictions
  useEffect(() => {
    if (!isLiveMode || useDemo || !predictions) return;

    if (predictions.type === 'prediction' && predictions.data.gesture && predictions.data.confidence) {
      triggerGestureTransition(predictions.data.gesture, predictions.data.confidence);
      if (predictions.data.latency) setLatency(predictions.data.latency);
      if (predictions.data.fps) setFps(predictions.data.fps);
    }
  }, [predictions, isLiveMode, useDemo, triggerGestureTransition]);

  // Live test mode: cycle gestures every 3 seconds
  useEffect(() => {
    if (!isLiveMode) {
      if (gestureIntervalRef.current) clearInterval(gestureIntervalRef.current);
      setIsPulsing(false);
      return;
    }

    // Immediately trigger first gesture
    const nextIdx = (currentGestureIdx + 1) % GESTURES.length;
    setCurrentGestureIdx(nextIdx);
    const nextGesture = GESTURES[nextIdx];
    const nextConfidence = 85 + Math.random() * 14;
    triggerGestureTransition(nextGesture, nextConfidence);

    gestureIntervalRef.current = setInterval(() => {
      setCurrentGestureIdx((prev) => {
        const idx = (prev + 1) % GESTURES.length;
        const g = GESTURES[idx];
        const c = 85 + Math.random() * 14;
        triggerGestureTransition(g, c);
        return idx;
      });
    }, 3000);

    return () => {
      if (gestureIntervalRef.current) clearInterval(gestureIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLiveMode]);

  // Subtle FPS/latency variation
  useEffect(() => {
    if (!isLiveMode) return;
    const interval = setInterval(() => {
      setFps(29.2 + Math.random() * 1.5);
      setLatency(130 + Math.floor(Math.random() * 30));
    }, 1500);
    return () => clearInterval(interval);
  }, [isLiveMode]);

  // Voice speaking when new transcript entry is added
  useEffect(() => {
    if (isVoiceActive && transcript.length > 0) {
      setIsSpeaking(true);
      const t = setTimeout(() => setIsSpeaking(false), 2200);
      return () => clearTimeout(t);
    }
  }, [transcript.length, isVoiceActive]);

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
        onToggleLiveMode={handleToggleLiveMode}
      />

      <main className="flex-1 p-4 md:p-6 flex flex-col gap-4">
        {/* Live mode banner */}
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
              LIVE TEST MODE ACTIVE — Cycling ASL gestures: {GESTURES.join(' → ')}
            </span>
            <span className="ml-auto font-mono-custom text-[10px] text-cyan-400/60">
              Interval: 3.0s
            </span>
          </motion.div>
        )}

        {/* Main grid */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left: Vision & Skeleton Studio (7/12) */}
          <div className="lg:col-span-7 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-md p-4 flex flex-col">
            <WebcamStudio
              isActive={isLiveMode}
              gesture={gesture}
              fps={fps}
              latency={latency}
            />
          </div>

          {/* Right: Neural Engine (5/12) */}
          <div className="lg:col-span-5 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-md p-4 overflow-hidden">
            <NeuralEngine
              isActive={isLiveMode}
              isPulsing={isPulsing}
              gesture={gesture}
              confidence={confidence}
              debounceProgress={debounceProgress}
              modelMetrics={{
                accuracy: '98.7%',
                latency: '142ms',
                inferenceHz: 30,
              }}
            />
          </div>
        </div>

        {/* Bottom dock */}
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
          {['TensorFlow.js', 'MediaPipe', 'WebGL', 'ASL2024'].map((tech) => (
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
