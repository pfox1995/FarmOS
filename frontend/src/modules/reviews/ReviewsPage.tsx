// Design Ref: §6.1 — ReviewsPage (Mock → API 연동 전환)
import { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { MdTrendingUp, MdStar, MdPlayArrow, MdSettings, MdDownload, MdWarning, MdStorage } from 'react-icons/md';
import { useReviewAnalysis } from '@/hooks/useReviewAnalysis';
import RAGSearchPanel from './RAGSearchPanel';
import AnalysisSettingsModal from './AnalysisSettingsModal';
import { REVIEWS, SENTIMENT_SUMMARY, KEYWORD_DATA, WEEKLY_TRENDS, AI_STRATEGIES } from '@/mocks/reviews';

const SENTIMENT_COLORS = { positive: '#16A34A', negative: '#DC2626', neutral: '#9CA3AF' };

export default function ReviewsPage() {
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [mounted, setMounted] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const {
    analysis, isLoading, isAnalyzing, isEmbedding,
    embedProgress, analyzeProgress, progressMessage,
    error, analyzeReviews, searchResults, isSearching, searchReviews,
    trends, anomalies, downloadReport, embedReviews,
    settings, updateSettings,
  } = useReviewAnalysis();

  // API 데이터가 있으면 사용, 없으면 Mock 데이터 폴백
  const sentimentSummary = analysis?.sentiment_summary || SENTIMENT_SUMMARY;
  const keywords = analysis?.keywords || KEYWORD_DATA;
  const weeklyTrends = trends.length > 0
    ? trends.map(t => ({ week: t.week, positive: t.positive, negative: t.negative, neutral: t.neutral }))
    : WEEKLY_TRENDS;
  const summary = analysis?.summary;
  const strategies = summary?.suggestions
    ? summary.suggestions.map((s, i) => ({ id: `sug-${i}`, title: s, description: '', priority: '중간' as const }))
    : AI_STRATEGIES;

  const filteredReviews = selectedPlatform === 'all'
    ? REVIEWS
    : REVIEWS.filter(r => r.platform === selectedPlatform);

  const avgRating = REVIEWS.length > 0
    ? (REVIEWS.reduce((sum, r) => sum + r.rating, 0) / REVIEWS.length).toFixed(1)
    : '0';

  const pieData = [
    { name: '긍정', value: sentimentSummary.positive, color: SENTIMENT_COLORS.positive },
    { name: '부정', value: sentimentSummary.negative, color: SENTIMENT_COLORS.negative },
    { name: '중립', value: sentimentSummary.neutral, color: SENTIMENT_COLORS.neutral },
  ];

  const hasAnalysis = !!analysis;

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => embedReviews()}
          disabled={isEmbedding}
          className="relative flex items-center gap-1.5 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors disabled:opacity-70 overflow-hidden"
        >
          {isEmbedding && (
            <span
              className="absolute left-0 top-0 h-full bg-blue-200/50 transition-all duration-300"
              style={{ width: `${embedProgress}%` }}
            />
          )}
          <MdStorage className="text-base relative z-10" />
          <span className="relative z-10">
            {isEmbedding ? `임베딩 ${embedProgress}%` : '임베딩 저장'}
          </span>
        </button>
        <button
          onClick={() => analyzeReviews('all', settings.default_batch_size)}
          disabled={isAnalyzing}
          className="relative flex items-center gap-1.5 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium disabled:opacity-70 hover:bg-primary/90 transition-colors overflow-hidden"
        >
          {isAnalyzing && (
            <span
              className="absolute left-0 top-0 h-full bg-white/20 transition-all duration-300"
              style={{ width: `${analyzeProgress}%` }}
            />
          )}
          <MdPlayArrow className="text-base relative z-10" />
          <span className="relative z-10">
            {isAnalyzing ? `분석 ${analyzeProgress}%` : 'AI 분석 실행'}
          </span>
        </button>
        {hasAnalysis && (
          <button
            onClick={downloadReport}
            className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
          >
            <MdDownload className="text-base" /> PDF 리포트
          </button>
        )}
        <button
          onClick={() => setShowSettings(true)}
          className="p-2 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors ml-auto"
        >
          <MdSettings className="text-lg" />
        </button>
      </div>

      {progressMessage && (isEmbedding || isAnalyzing) && (
        <div className="p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">{progressMessage}</div>
      )}

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Anomaly Alerts */}
      {anomalies.length > 0 && (
        <div className="space-y-2">
          {anomalies.map((a, i) => (
            <div key={i} className="flex items-center gap-2 p-3 bg-red-50 border border-red-100 rounded-lg">
              <MdWarning className="text-red-500 text-lg flex-shrink-0" />
              <span className="text-sm text-red-700">{a.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Analysis Meta */}
      {hasAnalysis && (
        <div className="text-xs text-gray-400 flex gap-3">
          <span>Provider: {analysis.llm_provider}</span>
          <span>Model: {analysis.llm_model}</span>
          <span>{analysis.processing_time_ms}ms</span>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="card !p-3 sm:!p-4 text-center">
          <p className="text-xs sm:text-sm text-gray-500">총 리뷰</p>
          <p className="text-2xl sm:text-3xl font-bold text-gray-900">{sentimentSummary.total}</p>
        </div>
        <div className="card !p-3 sm:!p-4 text-center">
          <p className="text-xs sm:text-sm text-gray-500">긍정률</p>
          <p className="text-2xl sm:text-3xl font-bold text-success">
            {sentimentSummary.total > 0 ? Math.round(sentimentSummary.positive / sentimentSummary.total * 100) : 0}%
          </p>
        </div>
        <div className="card !p-3 sm:!p-4 text-center">
          <p className="text-xs sm:text-sm text-gray-500">평균 평점</p>
          <p className="text-2xl sm:text-3xl font-bold text-amber-500">
            {avgRating} <MdStar className="inline text-amber-400" />
          </p>
        </div>
        <div className="card !p-3 sm:!p-4 text-center">
          <p className="text-xs sm:text-sm text-gray-500">AI 인사이트</p>
          <p className="text-2xl sm:text-3xl font-bold text-primary">{strategies.length}건</p>
        </div>
      </div>

      {/* AI Summary (from LLM) */}
      {summary?.overall && (
        <div className="card border-l-4 border-primary">
          <h3 className="section-title mb-2">AI 분석 요약</h3>
          <p className="text-sm text-gray-700">{summary.overall}</p>
          {summary.positives?.length > 0 && (
            <div className="mt-2">
              {summary.positives.map((p, i) => (
                <span key={i} className="inline-block mr-2 mb-1 px-2 py-0.5 bg-green-50 text-green-700 rounded text-xs">+ {p}</span>
              ))}
            </div>
          )}
          {summary.negatives?.length > 0 && (
            <div className="mt-1">
              {summary.negatives.map((n, i) => (
                <span key={i} className="inline-block mr-2 mb-1 px-2 py-0.5 bg-red-50 text-red-700 rounded text-xs">- {n}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment Pie Chart */}
        <div className="card">
          <h3 className="section-title mb-4">감성 분석</h3>
          {mounted && <div className="h-[260px] sm:h-[300px] overflow-hidden">
            <ResponsiveContainer width="100%" height="100%" debounce={50}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="45%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value">
                  {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip formatter={(value) => `${value}건`} />
                <Legend formatter={(value, entry: any) => `${value} ${entry.payload.value}건`} iconType="circle" iconSize={10} />
              </PieChart>
            </ResponsiveContainer>
          </div>}
        </div>

        {/* Weekly Trend */}
        <div className="card">
          <h3 className="section-title mb-4">주간 추이</h3>
          {mounted && <div className="h-[200px] sm:h-[250px] overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklyTrends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="positive" fill="#16A34A" name="긍정" radius={[4, 4, 0, 0]} />
                <Bar dataKey="negative" fill="#DC2626" name="부정" radius={[4, 4, 0, 0]} />
                <Bar dataKey="neutral" fill="#9CA3AF" name="중립" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>}
        </div>
      </div>

      {/* Keyword Cloud */}
      <div className="card">
        <h3 className="section-title mb-4">키워드 분석</h3>
        <div className="flex flex-wrap gap-2">
          {keywords.map(k => (
            <span
              key={k.word}
              className={`px-3 py-1.5 rounded-full font-medium ${
                k.sentiment === 'positive' ? 'bg-green-100 text-green-800' :
                k.sentiment === 'negative' ? 'bg-red-100 text-red-800' :
                'bg-gray-100 text-gray-700'
              }`}
              style={{ fontSize: `${Math.max(14, Math.min(22, 10 + k.count))}px` }}
            >
              {k.word} ({k.count})
            </span>
          ))}
        </div>
      </div>

      {/* RAG Search */}
      <RAGSearchPanel onSearch={searchReviews} results={searchResults} isSearching={isSearching} />

      {/* AI Strategy Recommendations */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <MdTrendingUp className="text-xl text-primary" />
          <h3 className="section-title">AI 판매 전략 추천</h3>
        </div>
        <div className="space-y-3">
          {strategies.map(s => (
            <div key={s.id} className="p-4 rounded-xl border border-gray-100 hover:border-primary/20 transition-colors">
              <div className="flex items-start justify-between">
                <h4 className="font-semibold text-gray-900">{s.title}</h4>
                <span className={`badge text-xs ${
                  s.priority === '높음' ? 'badge-danger' :
                  s.priority === '중간' ? 'badge-warning' : 'badge-info'
                }`}>
                  {s.priority}
                </span>
              </div>
              {s.description && <p className="text-sm text-gray-600 mt-2">{s.description}</p>}
            </div>
          ))}
        </div>
      </div>

      {/* Review List */}
      <div className="card">
        <div className="mb-4">
          <h3 className="section-title mb-3">리뷰 목록</h3>
          <div className="flex gap-2 flex-wrap">
            {['all', '네이버스마트스토어', '쿠팡'].map(p => (
              <button
                key={p}
                onClick={() => setSelectedPlatform(p)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer transition-colors ${
                  selectedPlatform === p ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {p === 'all' ? '전체' : p}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-2 max-h-[320px] sm:max-h-[400px] overflow-y-auto">
          {filteredReviews.map(r => (
            <div key={r.id} className="flex items-start gap-3 p-3 rounded-xl bg-gray-50">
              <span className={`mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                r.sentiment === 'positive' ? 'bg-success' :
                r.sentiment === 'negative' ? 'bg-danger' : 'bg-gray-400'
              }`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800">{r.text}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-400">{r.platform}</span>
                  <span className="text-xs text-amber-500">{'★'.repeat(r.rating)}</span>
                  <span className="text-xs text-gray-300">{r.date}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Settings Modal */}
      <AnalysisSettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        settings={settings}
        onSave={updateSettings}
      />
    </div>
  );
}
