"use client";

/**
 * Hands-free voice conversation built on the browser Web Speech API
 * (free, no extra backend): SpeechRecognition for STT, speechSynthesis for TTS.
 *
 * Loop: listening → (user finishes speaking) → processing → speaking → listening …
 * Barge-in: recognition keeps running while the assistant speaks; if the user
 * says something that is not an echo of the spoken answer, playback stops and
 * their words become the next question.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceState = "idle" | "listening" | "processing" | "speaking";

// Minimal typings — SpeechRecognition is not in TypeScript's DOM lib.
type RecognitionResult = { isFinal: boolean; 0: { transcript: string } };
type RecognitionEvent = { resultIndex: number; results: ArrayLike<RecognitionResult> };
type RecognitionErrorEvent = { error: string };
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => Recognition;

function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const LANG = "en-IN";

/** Strip markdown and split into short chunks (Chrome stalls on very long utterances). */
export function toSpeechChunks(text: string, maxLen = 220): string[] {
  const clean = text
    .replace(/\*\*|__|`|#+\s/g, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/\bArt\.\s/g, "Article ")
    .replace(/\s+/g, " ")
    .trim();
  const sentences = clean.match(/[^.!?;]+[.!?;]*/g) ?? [clean];
  const chunks: string[] = [];
  let current = "";
  for (const raw of sentences) {
    const sentence = raw.trim();
    if (!sentence) continue;
    if ((current + " " + sentence).length > maxLen && current) {
      chunks.push(current);
      current = sentence;
    } else {
      current = current ? `${current} ${sentence}` : sentence;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

const words = (t: string) => t.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(Boolean);

/** True if the heard text looks like the user talking rather than the mic picking up our own TTS. */
function isRealBargeIn(heard: string, spoken: string): boolean {
  const heardWords = words(heard);
  if (heardWords.length < 2) return false;
  const spokenSet = new Set(words(spoken));
  const overlap = heardWords.filter((w) => spokenSet.has(w)).length / heardWords.length;
  return overlap < 0.6;
}

function pickVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  const score = (v: SpeechSynthesisVoice) => {
    let s = 0;
    if (v.lang === "en-IN") s += 4;
    else if (v.lang.startsWith("en")) s += 2;
    if (/natural|neural|online|google/i.test(v.name)) s += 3;
    return s;
  };
  return [...voices].sort((a, b) => score(b) - score(a))[0] ?? null;
}

type Options = {
  /**
   * Called with the user's final utterance. Call `say(text)` to start speaking early (e.g. the
   * summary while the rest of the answer streams in); resolve to any remaining text to speak.
   */
  onUtterance: (text: string, say: (text: string) => void) => Promise<string | null>;
};

export function useVoiceConversation({ onUtterance }: Options) {
  const [state, setStateRaw] = useState<VoiceState>("idle");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState(false);

  const stateRef = useRef<VoiceState>("idle");
  const activeRef = useRef(false);
  const recRef = useRef<Recognition | null>(null);
  const recRunningRef = useRef(false);
  const finalTextRef = useRef("");
  const spokenTextRef = useRef("");
  const speechIdRef = useRef(0);
  const pendingRef = useRef(0); // utterances queued but not yet finished
  const replyDoneRef = useRef(true); // false while an answer may still add speech
  const turnRef = useRef(0); // bumps on every new question / interruption
  const onUtteranceRef = useRef(onUtterance);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  useEffect(() => {
    onUtteranceRef.current = onUtterance;
  }, [onUtterance]);

  const setState = (s: VoiceState) => {
    stateRef.current = s;
    setStateRaw(s);
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- feature detection must run on the client after hydration
    setSupported(!!getRecognitionCtor() && typeof window !== "undefined" && "speechSynthesis" in window);
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const load = () => {
      voiceRef.current = pickVoice();
    };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  const startRecognition = useCallback(() => {
    const rec = recRef.current;
    if (!rec || recRunningRef.current || !activeRef.current) return;
    try {
      rec.start();
      recRunningRef.current = true;
    } catch {
      // InvalidStateError if Chrome still considers it running; onend will retry.
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    speechIdRef.current += 1; // invalidates pending onend handlers
    turnRef.current += 1; // later speech from the interrupted answer is ignored
    pendingRef.current = 0;
    window.speechSynthesis?.cancel();
  }, []);

  const listen = useCallback(() => {
    if (!activeRef.current) return;
    finalTextRef.current = "";
    setInterim("");
    setState("listening");
    startRecognition();
  }, [startRecognition]);

  /** Called when a queued utterance finishes: once everything is spoken and the reply is complete, listen again. */
  const finishIfDone = useCallback(
    (id: number) => {
      if (id !== speechIdRef.current || stateRef.current !== "speaking") return;
      if (pendingRef.current > 0 || !replyDoneRef.current) return;
      // Drop the recognition session that ran during playback: it may still
      // finalize an echo of our own voice. onend restarts a fresh one.
      recRef.current?.abort();
      listen();
    },
    [listen]
  );

  /** Queue text for speech. Can be called repeatedly while an answer is still streaming in. */
  const enqueueSpeech = useCallback(
    (text: string) => {
      const synth = window.speechSynthesis;
      const chunks = toSpeechChunks(text);
      if (!synth || chunks.length === 0) return;
      const id = speechIdRef.current;
      if (stateRef.current !== "speaking") {
        spokenTextRef.current = "";
        finalTextRef.current = "";
        setInterim("");
        setState("speaking");
        startRecognition(); // keep the mic open during playback so the user can interrupt
      }
      spokenTextRef.current += ` ${text}`;
      for (const chunk of chunks) {
        const u = new SpeechSynthesisUtterance(chunk);
        u.lang = LANG;
        if (voiceRef.current) u.voice = voiceRef.current;
        u.rate = 1.03;
        pendingRef.current += 1;
        const done = () => {
          if (id !== speechIdRef.current) return;
          pendingRef.current = Math.max(0, pendingRef.current - 1);
          finishIfDone(id);
        };
        u.onend = done;
        u.onerror = (e) => {
          if (e.error !== "interrupted" && e.error !== "canceled") done();
        };
        synth.speak(u);
      }
    },
    [finishIfDone, startRecognition]
  );

  const handleFinal = useCallback(
    async (text: string) => {
      const turn = ++turnRef.current;
      replyDoneRef.current = false;
      pendingRef.current = 0;
      setState("processing");
      setInterim(text);
      const isCurrent = () => turn === turnRef.current && activeRef.current;
      const say = (part: string) => {
        if (isCurrent()) enqueueSpeech(part);
      };
      let reply: string | null = null;
      try {
        reply = await onUtteranceRef.current(text, say);
      } catch {
        reply = "Sorry, something went wrong. Please try again.";
      }
      if (!isCurrent()) return; // user interrupted or ended voice mode meanwhile
      replyDoneRef.current = true;
      if (reply) enqueueSpeech(reply);
      if (stateRef.current === "speaking") finishIfDone(speechIdRef.current);
      else listen();
    },
    [enqueueSpeech, finishIfDone, listen]
  );

  const ensureRecognition = useCallback(() => {
    if (recRef.current) return recRef.current;
    const Ctor = getRecognitionCtor();
    if (!Ctor) return null;
    const rec = new Ctor();
    rec.lang = LANG;
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = (e) => {
      let finalText = "";
      let interimText = "";
      for (let i = 0; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interimText += r[0].transcript;
      }
      const heard = (finalText + " " + interimText).trim();

      if (stateRef.current === "speaking") {
        if (!isRealBargeIn(heard, spokenTextRef.current)) return; // echo of our own voice
        stopSpeaking();
        setState("listening");
      }
      if (stateRef.current !== "listening") return;
      setInterim(heard);
      if (finalText.trim()) finalTextRef.current = finalText.trim();
    };

    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setError("Microphone access was blocked. Allow mic access in your browser to use voice mode.");
        activeRef.current = false;
        stopSpeaking();
        setState("idle");
      } else if (e.error === "audio-capture") {
        setError("No microphone was found.");
        activeRef.current = false;
        setState("idle");
      } else if (e.error === "network") {
        setError("Speech recognition needs an internet connection.");
        activeRef.current = false;
        setState("idle");
      }
      // "no-speech" / "aborted" are normal — onend restarts listening.
    };

    rec.onend = () => {
      recRunningRef.current = false;
      if (!activeRef.current) return;
      const finalText = finalTextRef.current;
      if (stateRef.current === "listening" && finalText) {
        finalTextRef.current = "";
        void handleFinal(finalText);
        return;
      }
      if (stateRef.current === "listening" || stateRef.current === "speaking") {
        setTimeout(startRecognition, 150);
      }
    };

    recRef.current = rec;
    return rec;
  }, [handleFinal, startRecognition, stopSpeaking]);

  const start = useCallback(() => {
    setError(null);
    if (!ensureRecognition()) {
      setError("Voice mode needs a browser with speech recognition (Chrome or Edge).");
      return;
    }
    // Unlock speech synthesis inside the user gesture (required by Safari/iOS).
    window.speechSynthesis?.speak(new SpeechSynthesisUtterance(""));
    activeRef.current = true;
    listen();
  }, [ensureRecognition, listen]);

  const stop = useCallback(() => {
    activeRef.current = false;
    stopSpeaking();
    recRef.current?.abort();
    recRunningRef.current = false;
    finalTextRef.current = "";
    setInterim("");
    setState("idle");
  }, [stopSpeaking]);

  /** Stop the assistant mid-sentence and go straight back to listening. */
  const interrupt = useCallback(() => {
    if (stateRef.current !== "speaking") return;
    stopSpeaking();
    listen();
  }, [listen, stopSpeaking]);

  useEffect(
    () => () => {
      activeRef.current = false;
      recRef.current?.abort();
      if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    },
    []
  );

  return { state, interim, error, supported, active: state !== "idle", start, stop, interrupt };
}
