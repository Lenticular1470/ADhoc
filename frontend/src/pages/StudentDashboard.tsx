import { useState, useRef, useEffect } from 'react'
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { LayoutDashboard, GraduationCap, FileText, Award, BookOpen, Map, LogOut, Search, Bell, Clock, CheckCircle, Building2, TrendingUp, AlertCircle, Upload, Calendar, ClipboardList,  Mic, } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useAnalytics } from '../hooks/useAnalytics'
import { apiFetch } from '../hooks/useApi'
import { VoiceTransportFactory, VoiceTransport } from '../services/voice/VoiceTransportFactory'
import MyScholarshipsPage from './MyScholarshipsPage'
import toast from 'react-hot-toast'
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function StudentHome() {
  const { callsOverTime, loading } = useAnalytics()
  const stats = [
    { label: 'Application status', value: 'Under review', icon: Clock, color: 'text-yellow-400' },
    { label: 'Scholarship match', value: '₹ 80,000 / yr', icon: Award, color: 'text-emerald-400' },
    { label: 'Next deadline', value: '15 Mar', icon: Calendar, color: 'text-purple-400' },
    { label: 'Recommended colleges', value: '8', icon: Building2, color: 'text-cyan-400' },
    { label: 'Semester progress', value: '62%', icon: TrendingUp, color: 'text-emerald-400' },
  ]
  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-bold text-white mb-1">Student Dashboard</h1><p className="text-zinc-400">Track your admissions, explore scholarships, and plan your academic journey.</p></div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {stats.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
            className="glass rounded-2xl p-5 hover:bg-white/10 transition-all">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">
                <stat.icon size={20} className={stat.color} />
              </div>
              <p className="text-xs text-zinc-500">{stat.label}</p>
            </div>
            <p className="text-2xl font-bold text-white">{stat.value}</p>
          </motion.div>
        ))}
      </div>
      <div className="glass rounded-2xl p-6">
        <h3 className="font-semibold text-white mb-4">Academic Progress</h3>
        {loading ? (
          <div className="h-48 flex items-center justify-center text-sm text-zinc-500">Loading analytics...</div>
        ) : callsOverTime.length > 0 ? (
          <div className="flex items-end justify-between gap-1 h-48">
            {callsOverTime.slice(-30).map((point, i) => {
              const maxCalls = Math.max(...callsOverTime.map((item) => item.calls), 1)
              const height = `${Math.max((point.calls / maxCalls) * 100, 8)}%`
              return (
                <motion.div key={`${point.date}-${i}`} className="flex-1 bg-gradient-to-t from-emerald-500/80 to-cyan-400/80 rounded-t-lg"
                  initial={{ height: 0 }} animate={{ height }} transition={{ delay: i * 0.02, duration: 0.5 }} />
              )
            })}
          </div>
        ) : (
          <div className="h-48 flex items-center justify-center text-sm text-zinc-500">No analytics available</div>
        )}
      </div>
    </div>
  )
}

function CareerAssistant() {
  const [messages, setMessages] = useState([
    { role: 'agent', text: 'Hello! I am your AI Career Assistant. Tell me about your interests and I will help you find the best career path.' },
    { role: 'user', text: 'I am interested in technology and programming.' },
    { role: 'agent', text: 'Great choice! Based on your interests, I recommend exploring: 1) Computer Science Engineering, 2) Data Science, 3) Artificial Intelligence. Would you like me to suggest colleges for these streams?' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [voiceState, setVoiceState] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')

  const [callStatus, setCallStatus] = useState<'idle' | 'connecting' | 'listening' | 'processing' | 'speaking'>('idle')
  const transportRef = useRef<VoiceTransport | null>(null)
  const sessionIdRef = useRef(`session_${Date.now()}`)

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    return () => {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(t => t.stop())
      }
    }
  }, [])

  const startListening = async () => {
    if (transportRef.current?.isConnected()) {
    await transportRef.current.disconnect()
    transportRef.current = null

    setVoiceState("idle")
    setCallStatus("idle")

    toast.success("Voice session ended")
    return
}

  try {
    setVoiceState("listening")
    setCallStatus("connecting")

    const backendUrl = "http://localhost:8000"
    sessionIdRef.current = `session_${Date.now()}`

    const statusResponse = await fetch(
      `${backendUrl}/api/voice/fastrtc-status`
    )

    const status = await statusResponse.json()

    const transport = VoiceTransportFactory.create(
      status.available && status.stream_ready ? "fastrtc" : "websocket",
      backendUrl
    )

    transportRef.current = transport

    transport.setEvents({
  onStateChange: (state) => {
    console.log("FastRTC:", state)

    if (state === "connected") {
      setVoiceState("listening")
      setCallStatus("listening")
      toast.success("Voice connected")
    }

    if (state === "disconnected") {
      setVoiceState("idle")
      setCallStatus("idle")
    }
  },

  onTranscript: (msg) => {
    const role =
      msg.role === "assistant" || msg.role === "agent"
        ? "agent"
        : "user"

    setMessages(prev => [
      ...prev,
      {
        role,
        text: msg.text,
      },
    ])
  },

  onAudio: () => {
    setVoiceState("speaking")
    setCallStatus("speaking")
  },

  onError: (err) => {
    console.error(err)
    toast.error("FastRTC Error")
  },

  onDisconnected: () => {
    transportRef.current = null
    setVoiceState("idle")
    setCallStatus("idle")
  },
})

await transport.connect(sessionIdRef.current)

  } catch (err) {
    console.error(err)
  }
  }

  const sendMessage = async (voiceText?: string) => {
    const userMessage = voiceText ?? input;

    if (!userMessage.trim() || loading) return;

    setMessages(prev => [...prev, { role: 'user', text: userMessage }]);
    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('token');

      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: 'career-assistant',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get AI response');
      }

      const data = await response.json();

      setMessages(prev => [
        ...prev,
        {
          role: 'agent',
          text: data.response,
        },
      ]);
      setLoading(false);

    } catch (error) {
      console.error(error);
      setLoading(false);
      setVoiceState('idle');

      setMessages(prev => [
        ...prev,
        {
          role: 'agent',
          text: 'Sorry, something went wrong while contacting the AI.',
        },
      ]);

      toast.error('Unable to contact the AI server. Please check your internet or try again.');
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold text-white tracking-tight mb-1">Career Assistant</h1>
      <p className="text-zinc-400">Get personalized career guidance from our AI.</p>
      <div className="glass-panel rounded-2xl p-6 h-[500px] flex flex-col border border-white/10 shadow-2xl">
        <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2 scrollbar-thin">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[75%] px-4 py-3 rounded-2xl shadow-lg transition-all ${
                msg.role === 'user' 
                  ? 'bg-gradient-to-r from-purple-600 via-pink-500 to-purple-500 text-white rounded-tr-none border border-white/10' 
                  : 'glass-panel text-zinc-200 rounded-tl-none border border-white/10'
              }`}>
                <p className="text-[10px] font-mono font-bold tracking-wider text-purple-400 mb-1.5">{msg.role === 'agent' ? 'AI ASSISTANT' : 'YOU'}</p>
                <div
  className="text-sm leading-relaxed overflow-x-auto
    [&_ul]:list-disc
    [&_ul]:ml-5
    [&_ol]:list-decimal
    [&_ol]:ml-5
    [&_li]:mb-1
    [&_p]:mb-2
    [&_strong]:font-semibold
    [&_strong]:text-white
    [&_table]:w-full
    [&_table]:border-collapse
    [&_table]:my-3
    [&_th]:border
    [&_th]:border-white/20
    [&_th]:px-3
    [&_th]:py-2
    [&_th]:text-left
    [&_th]:font-semibold
    [&_th]:text-white
    [&_td]:border
    [&_td]:border-white/20
    [&_td]:px-3
    [&_td]:py-2
    [&_td]:align-top"
>
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {msg.text}
  </ReactMarkdown>
</div>
              </div>
            </div>
          ))}
          {/* AI Typing */}
{loading && (
  <div className="flex justify-start">
    <div
      className="max-w-[75%] px-4 py-3 rounded-2xl shadow-lg glass-panel text-zinc-200 rounded-tl-none border border-white/10"
    >
      <p className="text-[10px] font-mono font-bold tracking-wider text-purple-400 mb-1.5">
        AI ASSISTANT
      </p>

      <div className="flex items-center gap-1">
        <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></span>
        <span
          className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
          style={{ animationDelay: "0.2s" }}
        ></span>
        <span
          className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
          style={{ animationDelay: "0.4s" }}
        ></span>
      </div>
    </div>
  </div>
)}
          <div ref={messagesEndRef} />
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={startListening}
            disabled={voiceState !== 'idle' && voiceState !== 'listening'}
            className={`self-stretch w-[48px] flex items-center justify-center shrink-0 rounded-xl border border-white/10 transition-all ${
              voiceState === 'listening'
                ? "bg-red-500/80 border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.7)] animate-pulse text-white"
                : voiceState !== 'idle'
                ? "bg-zinc-700/20 border-white/5 opacity-50 cursor-not-allowed text-zinc-500"
                : "bg-white/[0.03] hover:bg-gradient-to-r hover:from-purple-600 hover:via-pink-500 hover:to-purple-500 hover:border-purple-300/30 hover:shadow-[0_0_40px_rgba(139,92,246,0.3),0_0_80px_rgba(139,92,246,0.1)] text-white"
            }`}
          >
            <Mic className={voiceState === 'listening' ? 'text-white' : 'text-zinc-400 group-hover:text-white'} size={20} />
          </button>

          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            disabled={loading || voiceState !== 'idle'}
            placeholder={
              voiceState === 'listening'
                ? "Listening..."
                : voiceState === 'thinking'
                ? "Thinking..."
                : voiceState === 'speaking'
                ? "AI is speaking..."
                : "Ask about careers, courses, colleges..."
            }
            className="flex-1 bg-white/[0.03] border border-white/10 rounded-xl py-3 px-4 text-white placeholder-zinc-500 focus:outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 hover:border-white/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed" />

          <button
            onClick={() => sendMessage()}
            disabled={loading || voiceState !== 'idle'}
            className={`px-6 py-3 rounded-xl font-medium transition-all shadow-md border border-white/10 ${
              loading || voiceState !== 'idle'
                ? "bg-zinc-700 cursor-not-allowed opacity-60"
                : "bg-gradient-to-r from-purple-600 via-pink-500 to-purple-500 hover:border-purple-300/30 glow-purple"
            } text-white`}
          >
            {loading ? "Thinking..." : "Send"}
          </button>
        </div>
      </div>
      {callStatus !== 'idle' && (
  <p
    className={`mt-2 text-sm animate-pulse flex items-center gap-1.5 justify-center ${
      callStatus === 'connecting'
        ? 'text-yellow-400'
        : callStatus === 'listening'
        ? 'text-red-400'
        : callStatus === 'processing'
        ? 'text-orange-400'
        : 'text-cyan-400'
    }`}
  >
    {callStatus === 'connecting' && (
      <>
        <span className="w-2 h-2 rounded-full bg-yellow-400 animate-ping"></span>
        Connecting...
      </>
    )}

    {callStatus === 'listening' && (
      <>
        <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
        🎤 Listening...
      </>
    )}

    {callStatus === 'processing' && (
      <>
        <span className="w-2 h-2 rounded-full bg-orange-400 animate-ping"></span>
        ⚡ Processing...
      </>
    )}

    {callStatus === 'speaking' && (
      <>
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
        🤖 AI Speaking...
      </>
    )}
  </p>
)}
    </div>
  )
}

function AdmissionsTracker() {
  const stages = [
    { name: 'Application Submitted', status: 'completed', date: 'Jan 15, 2026' },
    { name: 'Document Verification', status: 'completed', date: 'Jan 18, 2026' },
    { name: 'Entrance Exam Score', status: 'completed', date: 'Feb 1, 2026' },
    { name: 'Interview Scheduled', status: 'in-progress', date: 'Mar 10, 2026' },
    { name: 'Final Decision', status: 'pending', date: 'Mar 25, 2026' },
  ]
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-white mb-1">Admissions Tracker</h1>
      <p className="text-zinc-400">Track your admission application status in real-time.</p>
      <div className="space-y-4">
        {stages.map((stage) => (
          <div key={stage.name} className="glass rounded-2xl p-5 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${stage.status === 'completed' ? 'bg-emerald-500/20' : stage.status === 'in-progress' ? 'bg-purple-500/20' : 'bg-white/5'}`}>
              {stage.status === 'completed' ? <CheckCircle size={20} className="text-emerald-400" /> : stage.status === 'in-progress' ? <Clock size={20} className="text-purple-400" /> : <AlertCircle size={20} className="text-zinc-500" />}
            </div>
            <div className="flex-1">
              <p className="text-white font-medium">{stage.name}</p>
              <p className="text-sm text-zinc-500">{stage.date}</p>
            </div>
            <span className={`text-xs px-3 py-1 rounded-full ${stage.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' : stage.status === 'in-progress' ? 'bg-purple-500/20 text-purple-400' : 'bg-white/5 text-zinc-500'}`}>
              {stage.status === 'completed' ? 'Completed' : stage.status === 'in-progress' ? 'In Progress' : 'Pending'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Scholarships() {
  const navigate = useNavigate()
  const [scholarships, setScholarships] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [applyingId, setApplyingId] = useState<string | null>(null)

  useEffect(() => {
    loadScholarships()
  }, [])

  const loadScholarships = async () => {
    try {
      const data = await apiFetch('/api/student/scholarships')
      setScholarships(data)
    } catch (e) {
      toast.error('Failed to load scholarships')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async (id: string) => {
    setApplyingId(id)
    try {
      const data = await apiFetch(`/api/student/scholarships/${id}/apply`, {
        method: 'POST'
      })
      if (data.success) {
        toast.success('Successfully applied for scholarship!')
        setScholarships(prev => prev.map(s => s.id === id ? { ...s, applied: true } : s))
        setTimeout(() => {
          navigate('/student/my-scholarships')
        }, 1000)
      } else {
        toast.error(data.message || 'Application failed')
      }
    } catch (e) {
      toast.error('Network error occurred')
    } finally {
      setApplyingId(null)
    }
  }

  if (loading) {
    return (
      <div className="h-64 flex flex-col items-center justify-center gap-4 text-zinc-500">
        <div className="w-10 h-10 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin" />
        <p className="font-medium">Discovering opportunities...</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-purple-100 to-white/70 mb-2">Scholarships</h1>
          <p className="text-zinc-400 font-medium">Discover and apply for financial aid programs tailored to your profile.</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {scholarships.map((s, i) => {
          const isClosed = s.application_end_date && new Date(s.application_end_date) < new Date()
          return (
            <motion.div key={s.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
              className={`relative group rounded-3xl p-[1px] overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl ${s.is_featured ? 'hover:shadow-amber-500/20' : 'hover:shadow-purple-500/20'}`}>
              
              {s.is_featured && (
                <div className="absolute inset-0 bg-gradient-to-br from-amber-500/30 via-orange-500/10 to-transparent opacity-50 group-hover:opacity-100 transition-opacity duration-500" />
              )}
              
              <div className="relative h-full glass rounded-3xl p-6 md:p-8 flex flex-col justify-between border border-white/5 bg-white/[0.02] backdrop-blur-xl">
                
                <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none" />
                
                <div className="relative z-10">
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <h3 className="font-bold text-white text-xl md:text-2xl leading-tight tracking-tight">{s.title}</h3>
                    <div className="flex flex-col gap-2 items-end shrink-0">
                      {s.is_featured && (
                        <span className="flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-400 border border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.2)]">
                          ★ Featured
                        </span>
                      )}
                      <span className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-full border ${isClosed ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}`}>
                        {isClosed ? 'Closed' : 'Active'}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 mb-6">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 text-zinc-300 text-xs font-medium border border-white/5">
                      <Building2 size={14} className="text-purple-400" />
                      {s.provider_name}
                    </div>
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 text-zinc-300 text-xs font-medium border border-white/5">
                      <Award size={14} className="text-pink-400" />
                      {s.scholarship_type}
                    </div>
                  </div>
                  
                  <div className="mb-6">
                    <p className="text-sm font-medium text-zinc-500 mb-1">Grant Amount</p>
                    <p className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-br from-emerald-400 via-cyan-400 to-teal-500 tracking-tight">
                      ₹{s.scholarship_amount.toLocaleString()}
                    </p>
                  </div>
                  
                  {s.eligibility_criteria && (
                    <div className="mb-6">
                      <p className="text-sm font-medium text-zinc-500 mb-1">Eligibility Criteria</p>
                      <p className="text-sm text-zinc-300 leading-relaxed">
                        {s.eligibility_criteria.length > 100 ? `${s.eligibility_criteria.substring(0, 100)}...` : s.eligibility_criteria}
                      </p>
                    </div>
                  )}
                </div>

                <div className="relative z-10 mt-2 pt-6 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-2 text-zinc-400 text-sm font-medium w-full md:w-auto">
                    <Calendar size={16} className={isClosed ? 'text-red-400' : 'text-emerald-400'} />
                    {s.application_end_date ? (
                       <span>Deadline: <span className="text-white">{new Date(s.application_end_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span></span>
                    ) : (
                       <span>No Deadline</span>
                    )}
                  </div>

                  <div className="w-full md:w-auto shrink-0">
                    {s.applied ? (
                      <button disabled className="w-full md:w-auto px-6 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-bold text-zinc-400 cursor-not-allowed flex items-center justify-center gap-2">
                        <CheckCircle size={16} className="text-emerald-500" /> Applied
                      </button>
                    ) : isClosed ? (
                      <button disabled className="w-full md:w-auto px-6 py-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-sm font-bold text-red-400 cursor-not-allowed">
                        Closed
                      </button>
                    ) : (
                      <button onClick={() => handleApply(s.id)} disabled={applyingId !== null}
                        className="w-full md:w-auto px-8 py-2.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 rounded-xl text-sm font-bold text-white shadow-lg shadow-purple-500/25 active:scale-95 transition-all flex items-center justify-center gap-2 group">
                        {applyingId === s.id ? (
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : 'Apply Now'}
                      </button>
                    )}
                  </div>
                </div>

              </div>
            </motion.div>
          )
        })}
        {scholarships.length === 0 && (
          <div className="col-span-1 xl:col-span-2 flex flex-col items-center justify-center py-20 px-4 glass rounded-3xl border border-white/5 bg-white/[0.01]">
            <Award size={48} className="text-zinc-600 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">No active scholarships</h3>
            <p className="text-zinc-400 text-center max-w-md">There are currently no open scholarships available. Check back later for new opportunities.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Roadmap() {
  const milestones = [
    { semester: 'Semester 1', courses: ['Programming Fundamentals', 'Mathematics I', 'Physics', 'Communication Skills'], completed: true },
    { semester: 'Semester 2', courses: ['Data Structures', 'Mathematics II', 'Digital Electronics', 'Environmental Science'], completed: true },
    { semester: 'Semester 3', courses: ['Algorithms', 'Database Systems', 'Computer Networks', 'Web Development'], completed: false },
    { semester: 'Semester 4', courses: ['Operating Systems', 'Software Engineering', 'Machine Learning Basics', 'Cloud Computing'], completed: false },
    { semester: 'Semester 5', courses: ['AI & Deep Learning', 'Big Data Analytics', 'Cybersecurity', 'Internship'], completed: false },
    { semester: 'Semester 6', courses: ['Capstone Project', 'Industry Training', 'Placement Preparation'], completed: false },
  ]
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-white mb-1">Academic Roadmap</h1>
      <p className="text-zinc-400">Your personalized academic journey from admission to placement.</p>
      <div className="space-y-4">
        {milestones.map((m, i) => (
          <motion.div key={m.semester} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }}
            className="glass rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${m.completed ? 'bg-emerald-500/20' : 'bg-purple-500/20'}`}>
                {m.completed ? <CheckCircle size={16} className="text-emerald-400" /> : <Map size={16} className="text-purple-400" />}
              </div>
              <h3 className="font-semibold text-white">{m.semester}</h3>
              {m.completed && <span className="text-xs text-emerald-400 ml-auto">Completed</span>}
            </div>
            <div className="flex flex-wrap gap-2">
              {m.courses.map(c => (
                <span key={c} className="px-3 py-1 rounded-full text-xs bg-white/5 text-zinc-300">{c}</span>
              ))}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

export default function StudentDashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const handleLogout = () => { logout(); toast.success('Signed out successfully'); navigate('/') }
  const navItems = [
    { path: '/student', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/student/career', label: 'Career Assistant', icon: GraduationCap },
    { path: '/student/admissions', label: 'Admissions Tracker', icon: FileText },
    { path: '/student/scholarships', label: 'Scholarships', icon: Award },
    { path: '/student/my-scholarships', label: 'My Scholarships', icon: ClipboardList },
    { path: '/student/roadmap', label: 'Roadmap', icon: Map },
  ]
  return (
    <div className="min-h-screen bg-transparent flex">
      <aside className="w-64 glass-panel border-r border-white/10 flex flex-col backdrop-blur-2xl">
        <div className="p-6">
          <Link to="/" className="flex items-center gap-2 group w-fit">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-cyan-400 flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
              <span className="text-white font-bold text-sm">A</span>
            </div>
            <span className="font-extrabold text-lg text-white">ADhoc<span className="text-gradient-neon font-black">.ai</span></span>
          </Link>
        </div>
        <nav className="flex-1 px-4 space-y-1">
          {navItems.map((item) => (
            <Link key={item.path} to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                location.pathname === item.path 
                  ? 'bg-gradient-to-r from-purple-500/15 to-cyan-500/5 border border-purple-500/25 text-white shadow-lg shadow-purple-500/5' 
                  : 'text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent'
              }`}>
              <item.icon size={18} />{item.label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t border-white/10">
          <div className="glass-panel rounded-xl p-4 mb-4 border border-white/5 bg-white/[0.01]">
            <p className="text-[10px] text-zinc-500 mb-1 font-mono tracking-wider">SIGNED IN</p>
            <p className="text-sm text-white truncate font-medium">{user?.email}</p>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-3 px-4 py-3 text-sm font-semibold text-zinc-400 hover:text-white hover:bg-white/5 rounded-xl transition-all w-full text-left">
            <LogOut size={18} />Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 flex flex-col">
        <header className="h-16 glass-panel border-b border-white/10 flex items-center justify-between px-6">
          <div className="flex-1 max-w-md">
            <div className="relative">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input type="text" placeholder="Search courses, scholarships..."
                className="w-full bg-white/[0.03] border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 hover:border-white/20 transition-all" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button className="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white border border-white/5 transition-all relative">
              <Bell size={18} /><span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </button>
            <button onClick={() => navigate('/student/profile')} className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-cyan-400 flex items-center justify-center text-white font-extrabold text-sm shadow-md hover:scale-105 active:scale-95 transition-transform" title="My Profile">
              {user?.full_name?.[0] || user?.email?.[0] || 'S'}
            </button>
          </div>
        </header>
        <div className="flex-1 p-6 overflow-auto bg-transparent">
          <Routes>
            <Route path="/" element={<StudentHome />} />
            <Route path="/career" element={<CareerAssistant />} />
             <Route path="/admissions" element={<AdmissionsTracker />} />
            <Route path="/scholarships" element={<Scholarships />} />
            <Route path="/my-scholarships" element={<MyScholarshipsPage />} />
            <Route path="/roadmap" element={<Roadmap />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}