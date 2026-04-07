import {
  useState,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from "react";
import { MdMic, MdStop, MdAutorenew, MdClose } from "react-icons/md";
import { motion, AnimatePresence } from "framer-motion";
import type { STTParseResult } from "@/types";

interface SpeechRecognitionEvent {
  results: {
    [index: number]: {
      [index: number]: { transcript: string };
      isFinal?: boolean;
    };
    length: number;
  };
  resultIndex: number;
}

interface Props {
  onParsed: (result: STTParseResult) => void;
  parseSTT: (rawText: string) => Promise<STTParseResult | null>;
}

export type STTStatus = "idle" | "recording" | "processing";

export interface STTInputHandle {
  start: () => void;
}

const STTInput = forwardRef<STTInputHandle, Props>(function STTInput(
  { onParsed, parseSTT },
  ref,
) {
  const [status, setStatus] = useState<STTStatus>("idle");
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<ReturnType<typeof createRecognition> | null>(
    null,
  );

  const startRecording = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;

    const recognition = new SR();
    recognition.lang = "ko-KR";
    recognition.continuous = true;
    recognition.interimResults = true;

    let finalTranscript = "";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result[0]) {
          if (result.isFinal) {
            finalTranscript += result[0].transcript + " ";
          } else {
            interim = result[0].transcript;
          }
        }
      }
      setTranscript(finalTranscript + interim);
    };

    recognition.onerror = () => {
      setStatus("idle");
      setTranscript("");
    };

    recognition.onend = () => {
      const text = finalTranscript.trim();
      if (text) {
        handleAnalyze(text);
      } else {
        setStatus("idle");
      }
    };

    recognition.start();
    recognitionRef.current = recognition;
    setStatus("recording");
    setTranscript("");
  }, []);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    const text = transcript.trim();
    if (text) {
      handleAnalyze(text);
    } else {
      setStatus("idle");
    }
  }, [transcript]);

  const handleAnalyze = useCallback(
    async (text: string) => {
      setStatus("processing");
      const result = await parseSTT(text);
      if (result) {
        onParsed(result);
      }
      setStatus("idle");
      setTranscript("");
    },
    [parseSTT, onParsed],
  );

  const handleCancel = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setStatus("idle");
    setTranscript("");
  }, []);

  useImperativeHandle(ref, () => ({ start: startRecording }), [startRecording]);

  const handleFABClick = useCallback(() => {
    if (status === "idle") {
      startRecording();
    } else if (status === "recording") {
      stopRecording();
    }
  }, [status, startRecording, stopRecording]);

  const isSupported =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);

  if (!isSupported) return null;

  return (
    <>
      {/* FAB */}
      {status === "idle" && (
        <button
          onClick={handleFABClick}
          className="fixed bottom-[88px] right-4 lg:bottom-8 lg:right-8 z-30
            h-12 px-5 rounded-full shadow-lg flex items-center justify-center gap-2
            bg-red-500 hover:bg-red-600 active:scale-95 cursor-pointer
            transition-colors duration-200"
        >
          <MdMic className="text-white text-xl" />
          <span className="text-white text-sm font-medium">영농일지 녹음</span>
        </button>
      )}

      {/* 녹음 중 / 분석 중 — 오버레이 */}
      <AnimatePresence>
        {(status === "recording" || status === "processing") && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]"
          >
            {/* 중앙 문구 */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              {status === "recording" && (
                <>
                  <p className="text-white text-lg font-medium">
                    녹음 중입니다...
                  </p>
                  {transcript && (
                    <div className="max-w-[300px] px-4 py-3 bg-white/90 rounded-xl">
                      <p className="text-xs text-gray-400 mb-1">인식 중</p>
                      <p className="text-sm text-gray-700 line-clamp-3">
                        {transcript}
                      </p>
                    </div>
                  )}
                </>
              )}
              {status === "processing" && (
                <>
                  <MdAutorenew className="text-white text-5xl animate-spin" />
                  <p className="text-white text-lg font-medium">
                    AI가 분석하고 있습니다...
                  </p>
                </>
              )}
            </div>

            {/* 취소 + 정지 버튼 — FAB과 동일한 위치 */}
            {status === "recording" && (
              <div className="fixed bottom-[88px] right-4 lg:bottom-8 lg:right-8 z-50 flex flex-col gap-2 items-end">
                <button
                  onClick={handleCancel}
                  className="h-12 px-5 rounded-full shadow-lg flex items-center justify-center gap-2
                    bg-white/90 cursor-pointer transition-colors hover:bg-white"
                >
                  <MdClose className="text-gray-600 text-xl" />
                  <span className="text-gray-600 text-sm font-medium">
                    녹음 취소
                  </span>
                </button>
                <button
                  onClick={stopRecording}
                  className="h-12 px-5 rounded-full shadow-lg flex items-center justify-center gap-2
                    bg-gray-700 cursor-pointer animate-pulse"
                >
                  <MdStop className="text-white text-xl" />
                  <span className="text-white text-sm font-medium">
                    녹음 중지
                  </span>
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
});

export default STTInput;

// Web Speech API 타입
function createRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  return new SR();
}

declare global {
  interface Window {
    SpeechRecognition: new () => {
      lang: string;
      continuous: boolean;
      interimResults: boolean;
      onresult: ((event: SpeechRecognitionEvent) => void) | null;
      onerror: ((event: unknown) => void) | null;
      onend: (() => void) | null;
      start: () => void;
      stop: () => void;
    };
    webkitSpeechRecognition: typeof window.SpeechRecognition;
  }
}
