import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams, useParams as useReactRouterParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MdSend, MdArrowBack, MdRefresh, MdSmartToy, MdPerson } from 'react-icons/md';
import toast from 'react-hot-toast';

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
    const escapeHtml = (value: string): string =>
      value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const formatInline = (value: string): string =>
      escapeHtml(value).replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');

    const normalizeLegacyPlaceholders = (value: string): string =>
      value
        .replace(/(?:\\)?\{\{\s*PEST_IDENTIFICATION_LINE\s*\}\}|(?:\\)?\{\s*PEST_IDENTIFICATION_LINE\s*\}|^PEST_IDENTIFICATION_LINE$/gm, '🔍 입력하신 이미지는 해충으로 인식되었습니다. 이를 기반으로 답변하겠습니다.')
        .replace(/(?:\\)?\{\{\s*PESTICIDE_HTML\s*\}\}|(?:\\)?\{\s*PESTICIDE_HTML\s*\}|^PESTICIDE_HTML$/gm, '<p class="my-2 text-gray-400 italic">권장 농약 정보가 누락되었습니다.</p>')
        .replace(/(?:\\)?\{\{\s*WEATHER_HTML\s*\}\}|(?:\\)?\{\s*WEATHER_HTML\s*\}|^WEATHER_HTML$/gm, '<p class="my-2 text-gray-400 italic">날씨 정보를 불러오지 못했습니다.</p>');

    // 텍스트 전처리
    let processedText = normalizeLegacyPlaceholders(text)
      .replace(/^\s*(##\s*)?⚠️ 공지/gm, '## ⚠️ 공지')
      .replace(/^\s*(-\s*)?현재 날씨:/gm, '- 현재 날씨:')
      .replace(/^\s*(-\s*)?조언:/gm, '- 조언:')
      .replace(/^\s*(-\s*)?성분\/제형:/gm, '- 성분/제형:')
      .replace(/^\s*(-\s*)?(사용 방법:|사용 시기:|희석 배수:|사용 횟수:)/gm, '    - $2')
      .replace(/^\s*(-\s*)?([^\n\-#]+ \[(?:[^\]]+)\])$/gm, '  - $2')
      .replace(/^-\s+-\s+/gm, '  - ');

    const lines = processedText.split('\n');
    const result: string[] = [];
    let inList = false;
    let inNestedList = false;
    let nestedLevel = 0; // 0: none, 1: '  -', 2: '    -'
    
    let inTable = false;
    let tableRows: string[][] = [];

    let inBlockquote = false;
    let blockquoteLines: string[] = [];

    const flushBlockquote = () => {
      if (!inBlockquote) return;
      result.push('<blockquote class="my-4 p-4 bg-gray-50 border-l-4 border-gray-300 rounded-r-xl italic text-gray-600 space-y-1">');
      blockquoteLines.forEach(l => {
        const content = formatInline(l.replace(/^-\s+/, '• '));
        result.push(`<p>${content}</p>`);
      });
      result.push('</blockquote>');
      inBlockquote = false;
      blockquoteLines = [];
    };

    const flushTable = () => {
      if (!inTable) return;
      if (tableRows.length < 2) {
        tableRows.forEach(row => result.push(`<p class="my-2">${formatInline(row.join(' | '))}</p>`));
      } else {
        result.push('<div class="my-4 overflow-x-auto rounded-xl border border-gray-200 shadow-sm">');
        result.push('<table class="min-w-full divide-y divide-gray-200 text-xs">');
        
        tableRows.forEach((row, idx) => {
          const isSeparator = idx === 1 && row.every(cell => /^[ \-:]+$/.test(cell));
          if (isSeparator) return;
          
          if (idx === 0) {
            result.push('<thead class="bg-gray-50"><tr>');
            row.forEach(cell => {
              const formatted = formatInline(cell.trim());
              result.push(`<th class="px-4 py-3 text-left font-bold text-gray-700 uppercase tracking-wider border-b border-gray-200">${formatted}</th>`);
            });
            result.push('</tr></thead><tbody class="bg-white divide-y divide-gray-100">');
          } else {
            result.push('<tr class="hover:bg-gray-50/50 transition-colors">');
            row.forEach(cell => {
              const formatted = formatInline(cell.trim());
              result.push(`<td class="px-4 py-2.5 text-gray-600 whitespace-nowrap">${formatted}</td>`);
            });
            result.push('</tr>');
          }
        });
        
        result.push('</tbody></table></div>');
      }
      inTable = false;
      tableRows = [];
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const nextLine = lines[i + 1] || '';

      const isTableLine = line.trim().startsWith('|') && line.trim().endsWith('|');
      
      if (isTableLine) {
        if (inBlockquote) flushBlockquote();
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        
        inTable = true;
        const cells = line.trim().split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableRows.push(cells);
        continue;
      } else if (inTable) {
        flushTable();
      }

      if (line.trim().startsWith('>')) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        
        inBlockquote = true;
        const content = line.trim().replace(/^>\s*/, '');
        blockquoteLines.push(content);
        continue;
      } else if (inBlockquote) {
        flushBlockquote();
      }

      if (line.startsWith('## ')) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        const content = line.replace(/^##\s+/, '').trim();
        result.push(`<h2 class="text-lg font-bold text-gray-800 mt-6 mb-3">${escapeHtml(content)}</h2>`);
        continue;
      }

      if (line.startsWith('### ')) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        const content = line.replace(/^###\s+/, '').trim();
        result.push(`<h3 class="text-base font-semibold text-gray-700 mt-4 mb-2">${escapeHtml(content)}</h3>`);
        continue;
      }

      if (/^\s{4,}-\s+.+/.test(line)) {
        if (!inList) { result.push('<ul class="my-1">'); inList = true; }
        if (nestedLevel === 0) { result.push('<li class="text-gray-800"><ul class="pl-4 mt-1 space-y-1">'); nestedLevel = 1; }
        if (nestedLevel === 1) { result.push('<li class="text-gray-800"><ul class="pl-4 mt-1 space-y-1 border-l-2 border-gray-100 ml-1">'); nestedLevel = 2; }
        
        const content = line.replace(/^\s{4,}-\s+/, '').trim();
        const formatted = formatInline(content);
        result.push(`<li class="text-gray-800 text-sm pl-4 relative before:content-[''] before:absolute before:-left-1 before:top-2 before:w-1 before:h-1 before:bg-gray-800 before:rounded-sm">${formatted}</li>`);

        if (!/^\s{4,}-\s+.+/.test(nextLine)) {
          result.push('</ul></li>');
          nestedLevel = 1;
        }
        continue;
      }

      if (/^\s{2,3}-\s+.+/.test(line)) {
        if (!inList) { result.push('<ul class="my-1">'); inList = true; }
        while (nestedLevel > 1) { result.push('</ul></li>'); nestedLevel--; }
        if (nestedLevel === 0) { result.push('<li class="text-gray-800"><ul class="pl-4 mt-1 space-y-1">'); nestedLevel = 1; }
        
        const content = line.replace(/^\s{2,3}-\s+/, '').trim();
        const formatted = formatInline(content);
        result.push(`<li class="text-gray-800 font-medium pl-3 mt-2 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1.5 before:h-1.5 before:border before:border-gray-800 before:rounded-full before:bg-transparent">${formatted}</li>`);

        if (!/^\s{2,}-\s+.+/.test(nextLine)) {
          result.push('</ul></li>');
          nestedLevel = 0;
        }
        continue;
      }

      if (/^-\s+.+/.test(line)) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (!inList) { result.push('<ul class="my-1 pl-4 list-none space-y-1">'); inList = true; }
        
        const content = line.replace(/^-\s+/, '').trim();
        const formatted = formatInline(content);
        result.push(`<li class="text-gray-800 mt-2 relative before:content-[''] before:absolute before:-left-3 before:top-2 before:w-1.5 before:h-1.5 before:bg-gray-800 before:rounded-full">${formatted}</li>`);

        if (!/^\s*-\s+.+/.test(nextLine)) {
          result.push('</ul>');
          inList = false;
        }
        continue;
      }

      // 일반 텍스트 (기존 HTML 허용 경로 제거 - XSS 방지)
      if (line.trim()) {
        while (nestedLevel > 0) { result.push('</ul></li>'); nestedLevel--; }
        if (inList) { result.push('</ul>'); inList = false; }
        const formatted = formatInline(line);
        result.push(`<p class="my-2">${formatted}</p>`);
      } else if (i > 0 && lines[i - 1].trim()) {
        if (lines[i-1].trim() !== '') {
          result.push('<br/>');
        }
      }
    }

    if (inTable) flushTable();
    if (inBlockquote) flushBlockquote();
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
  const [isLoading, setIsLoading] = useState(false);

  // API 호출 베이스 경로
  const API_BASE = 'http://localhost:8000/api/v1/diagnosis';

  // 1. 초기 컨텍스트 수신 (DiagnosisPage에서 보낸 데이터)
  const context = location.state?.diagnosisContext;
  const isHistory = location.state?.fromHistory === true;

  // DB에서 채팅 내역 불러오기
  const fetchChatMessages = async () => {
    if (!context?.id) return;
    setIsLoading(true);
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
      } else {
        toast.error("채팅 내역을 불러오는데 실패했습니다.");
      }
    } catch (err) {
      console.error("채팅 내역 조회 실패:", err);
      toast.error("채팅 내역을 불러오는데 실패했습니다. 서버 연결을 확인해주세요.");
    } finally {
      setIsLoading(false);
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
      } else {
        throw new Error('서버 응답 오류가 발생했습니다.');
      }
    } catch (err) {
      console.error("메시지 전송 실패:", err);
      toast.error("메시지 전송에 실패했습니다. 잠시 후 다시 시도해주세요.");
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
          <h2 className="font-bold text-gray-800">해충 AI 진단 센터</h2>
          <p className="text-[10px] text-primary font-bold uppercase tracking-wider">AI AGENT ACTIVE</p>
        </div>
        <button onClick={() => window.location.reload()} className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500">
          <MdRefresh className="text-xl" />
        </button>
      </div>

      {/* Chat Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-6 bg-gray-50/30">
        <AnimatePresence>
          {isLoading && messages.length === 0 && (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              className="flex flex-col items-center justify-center h-full space-y-4 py-20"
            >
              <div className="w-10 h-10 border-4 border-primary/20 border-t-primary rounded-full animate-spin" />
              <p className="text-sm text-gray-500 font-medium">대화 내용을 불러오는 중입니다...</p>
            </motion.div>
          )}
          
          {!isLoading && messages.length === 0 && (
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              className="flex flex-col items-center justify-center h-full space-y-3 py-20 opacity-60"
            >
              <MdSmartToy className="text-5xl text-gray-300" />
              <p className="text-sm text-gray-400">대화 내용이 없습니다.</p>
            </motion.div>
          )}

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
                        : 'bg-white text-gray-700 border-gray-100 rounded-tl-none'
                    }`}>
                      {msg.role === 'assistant' ? (
                        <div className="prose prose-sm max-w-none prose-p:my-0.5 prose-ul:my-1 prose-li:my-0.5">
                          <MarkdownRenderer content={msg.content} />
                        </div>
                      ) : (
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
          {isTyping && (
            <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start gap-3">
              <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center"><MdSmartToy /></div>
              <div className="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm flex flex-col gap-2 border border-gray-100">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:0.4s]" />
                </div>
                <p className="text-[11px] text-gray-400 font-medium leading-none">진단봇이 생각 중이에요. 잠시만 기다려 주세요...</p>
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
