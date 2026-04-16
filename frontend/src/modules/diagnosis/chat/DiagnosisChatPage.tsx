import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MdSend, MdArrowBack, MdRefresh, MdSmartToy, MdPerson } from 'react-icons/md';

interface Message {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  type?: 'loading' | 'text' | 'solution';
  data?: any;
}

// 마크다운 렌더러 컴포넌트 (개선된 파서)
function MarkdownRenderer({ content }: { content: string }) {
  const parseMarkdown = (text: string): string => {
    // 텍스트 전처리: LLM이 평문으로 응답할 경우를 대비해 특정 패턴에 마크다운 기호 주입
    let processedText = text
      .replace(/^\s*(##\s*)?⚠️ 공지/gm, '## ⚠️ 공지')
      .replace(/^\s*(-\s*)?현재 날씨:/gm, '- 현재 날씨:')
      .replace(/^\s*(-\s*)?조언:/gm, '- 조언:')
      .replace(/^\s*(-\s*)?성분\/제형:/gm, '- 성분/제형:')
      .replace(/^\s*(-\s*)?(사용 방법:|사용 시기:|희석 배수:|사용 횟수:)/gm, '    - $2')
      .replace(/^\s*(-\s*)?([^\n\-#]+ \[(?:[^\]]+)\])$/gm, '  - $2')
      .replace(/^-\s+-\s+/gm, '  - '); // 혹시나 '- - ' 같이 두 번 들어간 경우 방지

    const lines = processedText.split('\n');
    const result: string[] = [];
    let inList = false;
    let inNestedList = false;
    let nestedLevel = 0; // 0: none, 1: '  -', 2: '    -'

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const nextLine = lines[i + 1] || '';

      // H2: ## text (공지 포함)
      if (line.startsWith('## ')) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        const content = line.replace(/^##\s+/, '').trim();
        result.push(`<h2 class="text-lg font-bold text-gray-800 mt-4 mb-2">${content}</h2>`);
        continue;
      }

      // H3: ### text
      if (line.startsWith('### ')) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        const content = line.replace(/^###\s+/, '').trim();
        result.push(`<h3 class="text-base font-semibold text-gray-700 mt-3 mb-1">${content}</h3>`);
        continue;
      }

      // 2단계 중첩 리스트: '    - ' (공백 4개)
      if (/^\s{4,}-\s+.+/.test(line)) {
        if (!inList) { result.push('<ul class="my-1">'); inList = true; }
        if (nestedLevel === 0) { result.push('<li class="text-gray-800"><ul class="pl-4 mt-1 space-y-1">'); nestedLevel = 1; }
        if (nestedLevel === 1) { result.push('<li class="text-gray-800"><ul class="pl-4 mt-1 space-y-1 border-l-2 border-gray-100 ml-1">'); nestedLevel = 2; }
        
        const content = line.replace(/^\s{4,}-\s+/, '').trim();
        const formatted = content.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
        // 텍스트와 점 모두 진한 검은색
        result.push(`<li class="text-gray-800 text-sm pl-4 relative before:content-[''] before:absolute before:-left-1 before:top-2 before:w-1 before:h-1 before:bg-gray-800 before:rounded-sm">${formatted}</li>`);

        if (!/^\s{4,}-\s+.+/.test(nextLine)) {
          result.push('</ul></li>');
          nestedLevel = 1;
        }
        continue;
      }

      // 1단계 중첩 리스트: '  - ' (공백 2개)
      if (/^\s{2,3}-\s+.+/.test(line)) {
        if (!inList) { result.push('<ul class="my-1">'); inList = true; }
        while (nestedLevel > 1) { result.push('</ul></li>'); nestedLevel--; }
        if (nestedLevel === 0) { result.push('<li class="text-gray-800"><ul class="pl-4 mt-1 space-y-1">'); nestedLevel = 1; }
        
        const content = line.replace(/^\s{2,3}-\s+/, '').trim();
        const formatted = content.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
        // 텍스트와 속이 빈 원 테두리 모두 진한 검은색
        result.push(`<li class="text-gray-800 font-medium pl-3 mt-2 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:border before:border-gray-800 before:rounded-full before:bg-transparent">${formatted}</li>`);

        if (!/^\s{2,}-\s+.+/.test(nextLine)) {
          result.push('</ul></li>');
          nestedLevel = 0;
        }
        continue;
      }

      // 일반 리스트: '- '
      if (/^-\s+.+/.test(line)) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (!inList) { result.push('<ul class="my-1 pl-4 list-none space-y-1">'); inList = true; }
        
        const content = line.replace(/^-\s+/, '').trim();
        const formatted = content.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
        // 최상위 리스트 아이템은 검정색(어두운 회색) 꽉 찬 원
        result.push(`<li class="text-gray-800 mt-2 relative before:content-[''] before:absolute before:-left-3 before:top-2 before:w-1.5 before:h-1.5 before:bg-gray-800 before:rounded-full">${formatted}</li>`);

        if (!/^\s*-\s+.+/.test(nextLine)) {
          result.push('</ul>');
          inList = false;
        }
        continue;
      }

      // 일반 텍스트
      if (line.trim()) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        const formatted = line.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
        result.push(`<p class="my-2">${formatted}</p>`);
      } else if (i > 0 && lines[i - 1].trim()) {
        // 연속된 공백 줄은 무시
        if (lines[i-1].trim() !== '') {
          result.push('<br/>');
        }
      }
    }

    while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
    if (inList) result.push('</ul>');

    return result.join('');
  };

  return (
    <div
      className="markdown-content text-sm leading-relaxed"
      dangerouslySetInnerHTML={{ __html: parseMarkdown(content) }}
    />
  );
}

export default function DiagnosisChatPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  // API 호출 베이스 경로
  const API_BASE = 'http://localhost:8000/api/v1/diagnosis';

  // 1. 초기 컨텍스트 수신 (DiagnosisPage에서 보낸 데이터)
  const context = location.state?.diagnosisContext;
  const isHistory = location.state?.fromHistory === true;

  // DB에서 채팅 내역 불러오기
  const fetchChatMessages = async () => {
    if (!context?.id) return;
    try {
      const response = await fetch(`${API_BASE}/history/${context.id}/chat`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        // DB 메시지를 프론트엔드 형식으로 변환. 첫 번째 메시지는 솔루션 카드로 렌더링.
        const dbMessages: Message[] = data.map((m: any, idx: number) => ({
          id: m.id.toString(),
          role: m.role,
          content: m.content,
          type: (idx === 0 && m.role === 'assistant') ? 'solution' : 'text',
          data: { result_text: m.content }
        }));
        
        setMessages(dbMessages);
      }
    } catch (err) {
      console.error("채팅 내역 조회 실패:", err);
    }
  };

  useEffect(() => {
    if (!context) {
      navigate('/diagnosis');
      return;
    }

    // 진단이 막 생성되었거나, 히스토리에서 왔거나 상관없이
    // 이미 백엔드 생성 과정에서 초기 메시지가 DB에 저장되므로 DB에서 불러옴
    fetchChatMessages();
  }, [context]);

  // 스크롤 하단 이동
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSend = async () => {
    if (!inputValue.trim() || !context?.id) return;
    
    const userContent = inputValue;
    setInputValue('');
    
    // 임시 사용자 메시지 낙관적(Optimistic) UI 업데이트
    const tempId = `temp-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: tempId,
      role: 'user',
      content: userContent,
      type: 'text'
    }]);

    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE}/history/${context.id}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: 'user', content: userContent }),
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        
        setMessages(prev => {
          // 임시 메시지 제거
          const filtered = prev.filter(m => m.id !== tempId);
          const newMessages: typeof messages = [];
          
          if (data.user_msg) {
            newMessages.push({
              id: data.user_msg.id.toString(),
              role: 'user',
              content: data.user_msg.content,
              type: 'text'
            });
          } else if (data.id) {
            // fallback for older schema
            newMessages.push({
              id: data.id.toString(),
              role: data.role,
              content: data.content,
              type: 'text'
            });
          }
          
          if (data.ai_msg) {
            newMessages.push({
              id: data.ai_msg.id.toString(),
              role: 'assistant',
              content: data.ai_msg.content,
              type: 'text'
            });
          }
          
          return [...filtered, ...newMessages];
        });
      }
    } catch (err) {
      console.error("메시지 전송 실패:", err);
      // 실패 시 임시 메시지 복구/제거 처리
      setMessages(prev => prev.filter(m => m.id !== tempId));
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] max-w-4xl mx-auto bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-50 flex items-center justify-between bg-white sticky top-0 z-10">
        <button onClick={() => navigate('/diagnosis')} className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500">
          <MdArrowBack className="text-xl" />
        </button>
        <div className="flex flex-col items-center">
          <h2 className="font-bold text-gray-800">병해충 AI 진단 센터</h2>
          <p className="text-[10px] text-primary font-bold uppercase tracking-wider">AI AGENT ACTIVE</p>
        </div>
        <button onClick={() => window.location.reload()} className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500">
          <MdRefresh className="text-xl" />
        </button>
      </div>

      {/* Chat Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-6 bg-gray-50/30">
        <AnimatePresence>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  msg.role === 'assistant' ? 'bg-primary text-white' : 'bg-gray-200 text-gray-600'
                }`}>
                  {msg.role === 'assistant' ? <MdSmartToy /> : <MdPerson />}
                </div>
                
                <div className="space-y-2">
                  {msg.type === 'solution' ? (
                    <div className="space-y-4 w-full">
                      {/* 통합된 메인 텍스트 영역 (템플릿 엔진 출력물 - 마크다운 렌더링) */}
                      <div className="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm border border-gray-100 text-sm text-gray-700 leading-relaxed min-w-[280px] prose prose-sm max-w-none prose-headings:text-gray-800 prose-h2:text-lg prose-h2:font-bold prose-h2:mt-4 prose-h2:mb-2 prose-h3:text-base prose-h3:font-semibold prose-h3:mt-3 prose-h3:mb-1 prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 markdown-content">
                        <MarkdownRenderer content={msg.data?.result_text || msg.content || "분석 데이터를 불러오지 못했습니다."} />
                      </div>
                    </div>
                  ) : msg.type === 'loading' ? (
                    <div className="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-3">
                      <div className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
                      <p className="text-sm text-gray-400 font-medium">{msg.content}</p>
                    </div>
                  ) : (
                    <div className={`p-4 rounded-2xl shadow-sm border ${
                      msg.role === 'user' 
                        ? 'bg-primary text-white border-primary rounded-tr-none' 
                        : 'bg-white text-gray-700 border-gray-100 rounded-tl-none whitespace-pre-wrap'
                    }`}>
                      <p className="text-sm leading-relaxed">{msg.content}</p>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
          {isTyping && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start gap-3">
              <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center"><MdSmartToy /></div>
              <div className="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm flex gap-1">
                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce" />
                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce [animation-delay:0.4s]" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-gray-50">
        <div className="relative flex items-center gap-2 max-w-2xl mx-auto">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="추가 질문을 입력하세요..."
            className="flex-1 bg-gray-100 border-none rounded-2xl py-3.5 px-5 text-sm focus:ring-2 focus:ring-primary/20 outline-none transition-all"
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim()}
            className={`p-3.5 rounded-xl transition-all ${
              inputValue.trim() ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-gray-200 text-gray-400'
            }`}
          >
            <MdSend className="text-xl" />
          </button>
        </div>
        <p className="text-[10px] text-center text-gray-400 mt-2">AI 진단 결과에 따라 전문가와 상의 후 조치를 취하십시오.</p>
      </div>
    </div>
  );
}
