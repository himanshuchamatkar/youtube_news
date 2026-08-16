import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, Tv, FileText, Settings, Activity, Play, 
  RefreshCw, User, Lock, LogOut, AlertCircle, 
  ExternalLink, Clock, Video, Award, Users
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  ResponsiveContainer
} from 'recharts';

const API_BASE = 'http://localhost:8000';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('admin_token'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // App States
  const [systemStatus, setSystemStatus] = useState<any>({ status: 'Sleeping / Waking', database_connected: false });
  const [channelMetrics, setChannelMetrics] = useState<any>({ subscriber_count: 0, total_views: 0, total_videos: 0 });
  const [videoAnalytics, setVideoAnalytics] = useState<any[]>([]);
  const [newsHistory, setNewsHistory] = useState<any[]>([]);
  const [videoHistory, setVideoHistory] = useState<any[]>([]);
  const [jobsHistory, setJobsHistory] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<any>(null);
  
  // Settings Form States
  const [isTestMode, setIsTestMode] = useState(false);
  const [newGeminiKey, setNewGeminiKey] = useState('');
  const [geminiTestResult, setGeminiTestResult] = useState<string | null>(null);
  const [settingsUpdateMsg, setSettingsUpdateMsg] = useState<string | null>(null);
  const [settingsForm, setSettingsForm] = useState({
    daily_video_time: '11:00 AM',
    videos_per_day: 1,
    target_duration: '30-60 sec',
    language: 'English',
    youtube_privacy: 'public',
    minimum_news_score: 70,
    auto_upload: true,
    auto_voice: true,
    default_tts_voice: 'en-IN-Wavenet-C'
  });
  
  // News detail modal state
  const [selectedNews, setSelectedNews] = useState<any>(null);

  // Wake backend check interval / polling
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (token) {
      fetchSystemStatus();
      fetchChannelAnalytics();
      fetchNewsHistory();
      fetchVideoHistory();
      fetchJobsHistory();
      fetchAppSettings();
    }
  }, [token]);

  // Scroll to bottom of logs on updates
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [selectedJob?.logs]);

  // Job Polling hook
  useEffect(() => {
    let interval: any = null;
    if (pollingJobId && token) {
      interval = setInterval(() => {
        fetch(`${API_BASE}/api/jobs/${pollingJobId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(res => res.json())
        .then(data => {
          setSelectedJob(data);
          // Update the job list status
          setJobsHistory(prev => prev.map(j => j.id === data.id ? data : j));
          
          if (data.status === 'COMPLETED' || data.status === 'FAILED' || data.status === 'SKIPPED') {
            setPollingJobId(null);
            fetchVideoHistory();
            fetchChannelAnalytics();
          }
        })
        .catch(err => {
          console.error("Error polling job: ", err);
          setPollingJobId(null);
        });
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [pollingJobId, token]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (res.status === 200) {
        const data = await res.json();
        localStorage.setItem('admin_token', data.access_token);
        setToken(data.access_token);
      } else {
        const errData = await res.json();
        setLoginError(errData.detail || 'Login failed.');
      }
    } catch (err) {
      setLoginError('Failed to connect to backend.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    setToken(null);
  };

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 200) {
        const data = await res.json();
        setSystemStatus({ status: 'Online', ...data });
      } else if (res.status === 401) {
        handleLogout();
      }
    } catch (err) {
      setSystemStatus({ status: 'Sleeping / Waking', database_connected: false });
    }
  };

  const wakeBackend = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/wake`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'online') {
        fetchSystemStatus();
      }
    } catch (err) {
      alert("Failed to wake backend service.");
    }
  };

  const fetchChannelAnalytics = async () => {
    try {
      // Channel metrics cache check
      const res = await fetch(`${API_BASE}/api/analytics/channel`);
      const data = await res.json();
      setChannelMetrics(data);

      // Video analytics list
      const vRes = await fetch(`${API_BASE}/api/analytics/videos`);
      const vData = await vRes.json();
      if (Array.isArray(vData)) {
        setVideoAnalytics(vData);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchNewsHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/news`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setNewsHistory(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchVideoHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/videos`);
      const data = await res.json();
      if (Array.isArray(data)) {
        setVideoHistory(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchJobsHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/jobs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (Array.isArray(data)) {
        setJobsHistory(data);
        // Find if there is any running job to resume polling
        const running = data.find(j => j.status === 'RUNNING' || !['COMPLETED', 'FAILED', 'SKIPPED'].includes(j.status));
        if (running) {
          setPollingJobId(running.id);
          setSelectedJob(running);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAppSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setSettingsForm({
        daily_video_time: data.daily_video_time || '11:00 AM',
        videos_per_day: parseInt(data.videos_per_day || '1'),
        target_duration: data.target_duration || '30-60 sec',
        language: data.language || 'English',
        youtube_privacy: data.youtube_privacy || 'public',
        minimum_news_score: parseInt(data.minimum_news_score || '70'),
        auto_upload: data.auto_upload === 'true',
        auto_voice: data.auto_voice === 'true',
        default_tts_voice: data.default_tts_voice || 'en-IN-Wavenet-C'
      });
    } catch (err) {
      console.error(err);
    }
  };

  const triggerDailyPipeline = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/jobs/daily-news?is_test=${isTestMode}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setPollingJobId(data.job_id);
        setActiveTab('jobs');
        fetchJobsHistory();
      } else {
        alert(data.detail || "Pipeline failed to trigger.");
      }
    } catch (err) {
      alert("Error starting pipeline job.");
    }
  };

  const testGeminiKey = async () => {
    setGeminiTestResult('Testing...');
    try {
      const res = await fetch(`${API_BASE}/api/settings/gemini/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: newGeminiKey })
      });
      const data = await res.json();
      if (data.valid) {
        setGeminiTestResult('Valid Key!');
      } else {
        setGeminiTestResult('Invalid Key. Test failed.');
      }
    } catch (err) {
      setGeminiTestResult('Failed to connect to testing server.');
    }
  };

  const saveGeminiKey = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/gemini`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ api_key: newGeminiKey })
      });
      const data = await res.json();
      if (data.success) {
        alert("Gemini key replaced successfully!");
        setNewGeminiKey('');
        setGeminiTestResult(null);
        fetchAppSettings();
      }
    } catch (err) {
      alert("Failed to save key.");
    }
  };

  const updateAppSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSettingsUpdateMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(settingsForm)
      });
      const data = await res.json();
      if (data.success) {
        setSettingsUpdateMsg('Settings saved successfully!');
        fetchAppSettings();
      }
    } catch (err) {
      setSettingsUpdateMsg('Failed to update configurations.');
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md glass-panel p-8 rounded-2xl shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1.5 bg-finance-accent"></div>
          
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center justify-center gap-2">
              <TrendingUp className="text-finance-accent w-8 h-8" />
              Shorts Factory Admin
            </h1>
            <p className="text-sm text-finance-textMuted mt-1">Indian Stock Market Daily News AI Publisher</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-xs font-semibold text-finance-text uppercase tracking-wider mb-2">Username</label>
              <div className="relative">
                <User className="absolute left-3 top-3 w-5 h-5 text-finance-textMuted" />
                <input 
                  type="text" 
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-finance-dark/50 border border-yellow-500/20 focus:border-finance-accent/60 outline-none rounded-xl text-white placeholder-slate-600 transition-colors"
                  placeholder="admin"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-finance-text uppercase tracking-wider mb-2">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 w-5 h-5 text-finance-textMuted" />
                <input 
                  type="password" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-finance-dark/50 border border-yellow-500/20 focus:border-finance-accent/60 outline-none rounded-xl text-white placeholder-slate-600 transition-colors"
                  placeholder="••••••••••••"
                  required
                />
              </div>
            </div>

            {loginError && (
              <div className="bg-red-950/40 border border-red-500/30 text-red-400 text-xs px-4 py-3 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {loginError}
              </div>
            )}

            <button 
              type="submit"
              className="w-full py-3 bg-finance-accent hover:bg-yellow-500 text-finance-dark font-bold rounded-xl transition-all duration-300 shadow-lg shadow-yellow-500/10 hover:shadow-yellow-500/25 active:scale-95"
            >
              Sign In to Console
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Sidebar navigation */}
      <aside className="w-full md:w-64 glass-panel flex flex-col justify-between p-4 border-r border-yellow-500/10 shrink-0">
        <div>
          <div className="flex items-center gap-2 mb-8 px-2 py-3 border-b border-yellow-500/10">
            <TrendingUp className="text-finance-accent w-7 h-7" />
            <div>
              <h2 className="font-bold text-white text-sm tracking-wide">SHORTS FACTORY</h2>
              <span className="text-[10px] text-finance-success uppercase font-semibold">Indian Markets</span>
            </div>
          </div>

          <nav className="space-y-1.5">
            {[
              { id: 'dashboard', name: 'Dashboard', icon: Activity },
              { id: 'news', name: 'News History', icon: FileText },
              { id: 'videos', name: 'Video History', icon: Tv },
              { id: 'jobs', name: 'Jobs Console', icon: Clock },
              { id: 'settings', name: 'System Settings', icon: Settings },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${
                  activeTab === tab.id 
                    ? 'bg-finance-accent text-finance-dark shadow-lg shadow-yellow-500/10' 
                    : 'text-finance-textMuted hover:bg-finance-card/45 hover:text-white'
                }`}
              >
                <tab.icon className="w-5 h-5 shrink-0" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        <div className="pt-4 border-t border-yellow-500/10">
          <div className="flex items-center gap-2 mb-4 px-2">
            <span className={`w-2 h-2 rounded-full ${systemStatus.status === 'Online' ? 'bg-finance-success animate-pulse' : 'bg-finance-danger'}`} />
            <span className="text-xs text-finance-textMuted font-semibold">
              Backend: {systemStatus.status}
            </span>
            {systemStatus.status !== 'Online' && (
              <button onClick={wakeBackend} className="text-[10px] bg-finance-accent/20 text-finance-accent hover:bg-finance-accent/30 px-2 py-0.5 rounded font-bold uppercase ml-auto transition-colors">
                Wake
              </button>
            )}
          </div>
          
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 text-red-400 hover:bg-red-950/20 hover:text-red-300 rounded-xl text-sm font-semibold transition-colors"
          >
            <LogOut className="w-5 h-5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main dashboard content panel */}
      <main className="flex-1 p-6 md:p-10 overflow-y-auto max-w-6xl mx-auto w-full">
        {activeTab === 'dashboard' && (
          <div className="space-y-8">
            <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight text-white">Daily Overview</h1>
                <p className="text-sm text-finance-textMuted mt-1">Status cards, general analytics, and manual automation trigger.</p>
              </div>
              
              <div className="flex items-center gap-4">
                {/* Production / Test Mode Toggle Switch */}
                <div className="flex items-center bg-finance-card/80 p-1 rounded-xl border border-yellow-500/10 shrink-0">
                  <button 
                    onClick={() => setIsTestMode(false)}
                    className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${!isTestMode ? 'bg-finance-accent text-finance-dark shadow-md' : 'text-finance-textMuted hover:text-white'}`}
                  >
                    Production Mode
                  </button>
                  <button 
                    onClick={() => setIsTestMode(true)}
                    className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${isTestMode ? 'bg-finance-accent text-finance-dark shadow-md' : 'text-finance-textMuted hover:text-white'}`}
                  >
                    Test Mode
                  </button>
                </div>

                <button
                  onClick={triggerDailyPipeline}
                  disabled={!!pollingJobId}
                  className={`flex items-center gap-2 px-6 py-3 font-bold rounded-xl shadow-lg transition-all duration-300 ${
                    pollingJobId 
                      ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                      : 'bg-finance-accent hover:bg-yellow-500 text-finance-dark shadow-yellow-500/10 hover:shadow-yellow-500/25 active:scale-95'
                  }`}
                >
                  <Play className="w-5 h-5 shrink-0" />
                  {pollingJobId ? 'Job Running...' : (isTestMode ? "Run Test Script" : "Run Today's Script")}
                </button>
              </div>
            </header>

            {/* Statistics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {[
                { title: 'Subscribers', value: channelMetrics.subscriber_count.toLocaleString(), icon: Users, color: 'text-blue-400 border-blue-500/20' },
                { title: 'Total Views', value: channelMetrics.total_views.toLocaleString(), icon: Tv, color: 'text-finance-success border-green-500/20' },
                { title: 'Shorts Published', value: channelMetrics.total_videos, icon: Video, color: 'text-purple-400 border-purple-500/20' },
                { title: 'Quality Threshold', value: '70 / 100', icon: Award, color: 'text-finance-accent border-yellow-500/20' },
              ].map((stat, idx) => (
                <div key={idx} className={`glass-panel p-6 rounded-2xl border ${stat.color} flex items-center justify-between`}>
                  <div>
                    <span className="text-xs font-bold text-finance-textMuted uppercase tracking-wider">{stat.title}</span>
                    <h3 className="text-2xl font-black text-white mt-1.5">{stat.value}</h3>
                  </div>
                  <stat.icon className={`w-10 h-10 ${stat.color.split(' ')[0]} opacity-80`} />
                </div>
              ))}
            </div>

            {/* Video analytics chart */}
            {videoAnalytics.length > 0 && (
              <div className="glass-panel p-6 rounded-2xl border border-yellow-500/10">
                <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                  <TrendingUp className="text-finance-accent w-5 h-5" />
                  Views Trend - Recent Shorts
                </h3>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={videoAnalytics.slice().reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(241, 196, 15, 0.05)" />
                      <XAxis dataKey="title" tickFormatter={(t) => t.split(' | ')[0].slice(0, 15) + '...'} stroke="#8892b0" fontSize={11} />
                      <YAxis stroke="#8892b0" fontSize={11} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#112240', border: '1px solid rgba(241, 196, 15, 0.2)', color: '#f8f9fa' }}
                        labelFormatter={(t) => t}
                      />
                      <Line type="monotone" dataKey="views" stroke="#2ecc71" strokeWidth={3} dot={{ fill: '#2ecc71', r: 5 }} activeDot={{ r: 8 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Dashboard lists */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Recent videos list */}
              <div className="glass-panel p-6 rounded-2xl border border-yellow-500/10">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-white text-base">Latest Videos</h3>
                  <button onClick={() => setActiveTab('videos')} className="text-xs text-finance-accent hover:underline">View All</button>
                </div>
                <div className="space-y-4">
                  {videoHistory.slice(0, 4).map((vid) => (
                    <div key={vid.id} className="flex items-center justify-between p-3.5 bg-finance-dark/45 border border-yellow-500/5 hover:border-yellow-500/15 rounded-xl transition-all">
                      <div className="min-w-0 flex-1 pr-4">
                        <h4 className="font-bold text-sm text-white truncate">{vid.title}</h4>
                        <span className="text-[10px] text-finance-textMuted mt-1 block flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5" />
                          {new Date(vid.published_at).toLocaleDateString()} &bull; {vid.duration}s
                        </span>
                      </div>
                      <a 
                        href={vid.youtube_url} 
                        target="_blank" 
                        rel="noreferrer"
                        className="p-2.5 bg-finance-accent/10 hover:bg-finance-accent text-finance-accent hover:text-finance-dark rounded-lg transition-all"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  ))}
                  {videoHistory.length === 0 && (
                    <div className="text-center py-8 text-finance-textMuted text-sm">No videos generated yet. Trigger script to start!</div>
                  )}
                </div>
              </div>

              {/* Top Qualifying News candidates list */}
              <div className="glass-panel p-6 rounded-2xl border border-yellow-500/10">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="font-bold text-white text-base">Top News Candidates</h3>
                  <button onClick={() => setActiveTab('news')} className="text-xs text-finance-accent hover:underline">View All</button>
                </div>
                <div className="space-y-4">
                  {newsHistory.slice(0, 4).map((news) => (
                    <div key={news.id} className="flex items-center justify-between p-3.5 bg-finance-dark/45 border border-yellow-500/5 rounded-xl">
                      <div className="min-w-0 flex-1 pr-4">
                        <h4 className="font-bold text-sm text-white truncate">{news.title}</h4>
                        <p className="text-[10px] text-finance-textMuted truncate mt-0.5">{news.source} &bull; {news.provider.toUpperCase()}</p>
                      </div>
                      <div className="shrink-0 flex items-center gap-2">
                        <span className={`text-[10px] font-bold px-2 py-1 rounded ${
                          news.relevance_score >= 70 ? 'bg-green-950/50 text-finance-success border border-green-500/20' : 'bg-red-950/50 text-finance-danger border border-red-500/20'
                        }`}>
                          Score: {news.relevance_score}
                        </span>
                      </div>
                    </div>
                  ))}
                  {newsHistory.length === 0 && (
                    <div className="text-center py-8 text-finance-textMuted text-sm">No raw news items available. Trigger pipeline to scan.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'news' && (
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-extrabold text-white">Scraped News History</h1>
              <p className="text-sm text-finance-textMuted mt-1">Raw feeds ingested, relevance check filters, and duplicate matching indices.</p>
            </div>

            <div className="glass-panel rounded-2xl border border-yellow-500/10 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-yellow-500/10 bg-finance-card/45 text-xs font-bold text-finance-text uppercase tracking-wider">
                      <th className="py-4 px-6">Headline</th>
                      <th className="py-4 px-6">Source</th>
                      <th className="py-4 px-6">Fetched Time</th>
                      <th className="py-4 px-6 text-center">Score</th>
                      <th className="py-4 px-6 text-center">Selection Status</th>
                      <th className="py-4 px-6 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-yellow-500/5 text-sm">
                    {newsHistory.map((item) => (
                      <tr key={item.id} className="hover:bg-finance-card/25 transition-colors">
                        <td className="py-4 px-6 max-w-sm">
                          <div className="font-bold text-white truncate">{item.title}</div>
                          {item.duplicate_of && (
                            <span className="text-[10px] bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded mt-1 inline-block">Duplicate story</span>
                          )}
                        </td>
                        <td className="py-4 px-6 text-finance-textMuted">
                          {item.source} <span className="text-[10px] bg-yellow-500/5 text-finance-accent border border-yellow-500/10 px-1.5 py-0.5 rounded ml-1 uppercase">{item.provider}</span>
                        </td>
                        <td className="py-4 px-6 text-finance-textMuted text-xs">
                          {new Date(item.fetched_at).toLocaleString()}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <span className={`text-xs font-bold px-2.5 py-1 rounded ${
                            item.relevance_score >= 70 ? 'bg-green-950/40 text-finance-success border border-green-500/20' : 'bg-red-950/40 text-finance-danger border border-red-500/20'
                          }`}>
                            {item.relevance_score}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-center">
                          <span className={`text-xs font-semibold uppercase px-2 py-1 rounded ${
                            item.status === 'selected' ? 'bg-yellow-500/10 text-finance-accent border border-yellow-500/20' : 'text-finance-textMuted bg-zinc-950/30'
                          }`}>
                            {item.status}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-center">
                          <button 
                            onClick={() => setSelectedNews(item)}
                            className="text-xs text-finance-accent hover:underline font-bold"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    ))}
                    {newsHistory.length === 0 && (
                      <tr>
                        <td colSpan={6} className="text-center py-12 text-finance-textMuted">No ingested news items in database history.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* News detail modal */}
            {selectedNews && (
              <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                <div className="w-full max-w-2xl glass-panel p-8 rounded-2xl shadow-2xl relative border border-yellow-500/20 max-h-[85vh] overflow-y-auto">
                  <button 
                    onClick={() => setSelectedNews(null)}
                    className="absolute top-4 right-4 text-finance-textMuted hover:text-white font-bold text-xl"
                  >
                    &times;
                  </button>
                  <h3 className="text-xl font-bold text-white pr-6">{selectedNews.title}</h3>
                  <div className="flex gap-4 text-xs text-finance-textMuted mt-2 border-b border-yellow-500/10 pb-4">
                    <span>Source: {selectedNews.source} ({selectedNews.provider.toUpperCase()})</span>
                    <span>Published: {new Date(selectedNews.published_at).toLocaleString()}</span>
                  </div>
                  <div className="space-y-4 mt-6">
                    <div>
                      <h4 className="text-xs font-bold text-finance-accent uppercase tracking-wider">Description</h4>
                      <p className="text-finance-text text-sm mt-1 leading-relaxed">{selectedNews.description || 'No description provided.'}</p>
                    </div>
                    {selectedNews.company && (
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <h4 className="text-xs font-bold text-finance-accent uppercase">Company</h4>
                          <p className="text-white text-sm mt-0.5">{selectedNews.company}</p>
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-finance-accent uppercase">Sector</h4>
                          <p className="text-white text-sm mt-0.5">{selectedNews.sector}</p>
                        </div>
                      </div>
                    )}
                    <div>
                      <h4 className="text-xs font-bold text-finance-accent uppercase tracking-wider">Original Source Link</h4>
                      <a 
                        href={selectedNews.url} 
                        target="_blank" 
                        rel="noreferrer"
                        className="text-blue-400 hover:underline text-xs flex items-center gap-1.5 mt-1"
                      >
                        {selectedNews.url}
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'videos' && (
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-extrabold text-white">Published Video History</h1>
              <p className="text-sm text-finance-textMuted mt-1">List of all daily news Shorts generated, durations, and YouTube publish logs.</p>
            </div>

            <div className="glass-panel rounded-2xl border border-yellow-500/10 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-yellow-500/10 bg-finance-card/45 text-xs font-bold text-finance-text uppercase tracking-wider">
                      <th className="py-4 px-6">Video Title</th>
                      <th className="py-4 px-6">Published Date</th>
                      <th className="py-4 px-6 text-center">Duration</th>
                      <th className="py-4 px-6">YouTube URL</th>
                      <th className="py-4 px-6 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-yellow-500/5 text-sm">
                    {videoHistory.map((video) => (
                      <tr key={video.id} className="hover:bg-finance-card/25 transition-colors">
                        <td className="py-4 px-6 font-bold text-white max-w-sm">
                          {video.title}
                        </td>
                        <td className="py-4 px-6 text-finance-textMuted text-xs">
                          {new Date(video.published_at).toLocaleString()}
                        </td>
                        <td className="py-4 px-6 text-center text-finance-text font-semibold">
                          {video.duration}s
                        </td>
                        <td className="py-4 px-6">
                          {video.youtube_url || video.status === 'test' ? (
                            <a 
                              href={video.status === 'test' ? `${API_BASE}/api/jobs/${video.job_id}/video` : video.youtube_url} 
                              target="_blank" 
                              rel="noreferrer"
                              className="text-blue-400 hover:underline flex items-center gap-1.5 text-xs font-semibold"
                            >
                              {video.status === 'test' ? 'Preview Test Video' : video.youtube_url}
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          ) : (
                            <span className="text-zinc-600 italic">No Link</span>
                          )}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <span className={`text-xs font-bold px-2 py-1 rounded ${
                            video.status === 'uploaded' ? 'bg-green-950/40 text-finance-success border border-green-500/20' : 
                            video.status === 'test' ? 'bg-yellow-950/40 text-finance-accent border border-yellow-500/20' : 
                            'bg-red-950/40 text-finance-danger border border-red-500/20'
                          }`}>
                            {video.status.toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {videoHistory.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center py-12 text-finance-textMuted">No published videos found in history.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="space-y-8">
            <div>
              <h1 className="text-3xl font-extrabold text-white">Channel Analytics</h1>
              <p className="text-sm text-finance-textMuted mt-1">YouTube Stats cache, subscriber counts, total views, and video-by-video details.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {[
                { title: 'Subscribers', value: channelMetrics.subscriber_count.toLocaleString(), icon: Users },
                { title: 'Total Channel Views', value: channelMetrics.total_views.toLocaleString(), icon: Tv },
                { title: 'Shorts Count', value: channelMetrics.total_videos, icon: Video },
              ].map((stat, idx) => (
                <div key={idx} className="glass-panel p-6 rounded-2xl border border-yellow-500/10 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-finance-textMuted uppercase tracking-wider">{stat.title}</span>
                    <h3 className="text-2xl font-black text-white mt-1">{stat.value}</h3>
                  </div>
                  <stat.icon className="w-8 h-8 text-finance-accent opacity-80" />
                </div>
              ))}
            </div>

            {/* Video wise table */}
            <div className="glass-panel p-6 rounded-2xl border border-yellow-500/10">
              <h3 className="text-lg font-bold text-white mb-6">Video-wise Performance</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-yellow-500/10 bg-finance-card/45 text-xs font-bold uppercase text-finance-text tracking-wider">
                      <th className="py-4 px-6">Video Title</th>
                      <th className="py-4 px-6 text-center">Views</th>
                      <th className="py-4 px-6 text-center">Likes</th>
                      <th className="py-4 px-6 text-center">Comments</th>
                      <th className="py-4 px-6 text-center">Link</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-yellow-500/5">
                    {videoAnalytics.map((video) => (
                      <tr key={video.id} className="hover:bg-finance-card/25 transition-colors">
                        <td className="py-4 px-6 font-semibold text-white max-w-xs truncate">
                          {video.title}
                        </td>
                        <td className="py-4 px-6 text-center font-bold text-finance-success">
                          {video.views}
                        </td>
                        <td className="py-4 px-6 text-center font-bold text-blue-400">
                          {video.likes}
                        </td>
                        <td className="py-4 px-6 text-center font-bold text-purple-400">
                          {video.comments}
                        </td>
                        <td className="py-4 px-6 text-center">
                          <a 
                            href={video.youtube_url} 
                            target="_blank" 
                            rel="noreferrer"
                            className="text-finance-accent hover:underline flex items-center justify-center gap-1 text-xs"
                          >
                            YouTube <ExternalLink className="w-3 h-3" />
                          </a>
                        </td>
                      </tr>
                    ))}
                    {videoAnalytics.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center py-8 text-finance-textMuted">No video analytics data cached. Make sure keys are configured and videos are uploaded.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'jobs' && (
          <div className="space-y-8">
            <div>
              <h1 className="text-3xl font-extrabold text-white">Jobs Console</h1>
              <p className="text-sm text-finance-textMuted mt-1">Monitor real-time logs, pipeline stages, and execution trace paths.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Job history panel */}
              <div className="lg:col-span-1 glass-panel p-6 rounded-2xl border border-yellow-500/10 space-y-4 max-h-[70vh] overflow-y-auto">
                <h3 className="font-bold text-white text-base border-b border-yellow-500/10 pb-3">Pipeline Jobs</h3>
                <div className="space-y-3">
                  {jobsHistory.map((job) => (
                    <button
                      key={job.id}
                      onClick={() => {
                        setSelectedJob(job);
                        if (job.status === 'RUNNING') {
                          setPollingJobId(job.id);
                        } else {
                          setPollingJobId(null);
                        }
                      }}
                      className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                        selectedJob?.id === job.id 
                          ? 'bg-finance-accent/15 border-finance-accent' 
                          : 'bg-finance-dark/45 border-yellow-500/5 hover:border-yellow-500/15'
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <span className="font-bold text-white text-xs tracking-wider uppercase">Job: {job.job_date}</span>
                        <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded ${
                          job.status === 'COMPLETED' ? 'bg-green-950 text-finance-success border border-green-500/20' :
                          job.status === 'FAILED' ? 'bg-red-950 text-finance-danger border border-red-500/20' :
                          job.status === 'SKIPPED' ? 'bg-zinc-800 text-zinc-400' : 'bg-yellow-950 text-finance-accent border border-yellow-500/20 animate-pulse'
                        }`}>
                          {job.status}
                        </span>
                      </div>
                      <p className="text-[10px] text-finance-textMuted mt-2">Started: {new Date(job.started_at).toLocaleTimeString()}</p>
                    </button>
                  ))}
                  {jobsHistory.length === 0 && (
                    <div className="text-center py-12 text-finance-textMuted text-sm">No job records found.</div>
                  )}
                </div>
              </div>

              {/* Progress and Live logs panel */}
              <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-yellow-500/10 flex flex-col justify-between max-h-[70vh]">
                {selectedJob ? (
                  <div className="flex flex-col h-full justify-between">
                    <div>
                      <div className="flex justify-between items-start border-b border-yellow-500/10 pb-4 mb-4">
                        <div>
                          <h3 className="font-bold text-white text-base">Execution Details: {selectedJob.job_date}</h3>
                          <p className="text-xs text-finance-textMuted mt-0.5">Stage: <span className="text-white font-semibold">{selectedJob.current_stage}</span></p>
                        </div>
                        {selectedJob.status === 'RUNNING' && (
                          <div className="flex items-center gap-1.5 text-xs text-finance-accent animate-pulse font-bold">
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            Live Processing
                          </div>
                        )}
                      </div>

                      {/* Progress bar */}
                      <div className="mb-6">
                        <div className="flex justify-between text-xs font-bold text-finance-textMuted mb-2">
                          <span>Pipeline Progress</span>
                          <span className="text-white">{selectedJob.progress}%</span>
                        </div>
                        <div className="w-full bg-finance-dark/70 rounded-full h-2 overflow-hidden border border-yellow-500/5">
                          <div 
                            className="bg-finance-accent h-full rounded-full transition-all duration-500"
                            style={{ width: `${selectedJob.progress}%` }}
                          />
                        </div>
                      </div>

                      {/* Live Logs output terminal */}
                      <h4 className="text-xs font-bold text-finance-text uppercase tracking-wider mb-2">Stage Diagnostics Log</h4>
                      <div className="bg-black/80 rounded-xl p-4 font-mono text-xs overflow-y-auto h-72 border border-yellow-500/10 space-y-2.5">
                        {selectedJob.logs && selectedJob.logs.map((log: any, idx: number) => (
                          <div key={log.id || idx} className="border-b border-zinc-900 pb-2">
                            <span className="text-slate-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{' '}
                            <span className={`font-bold ${
                              log.status === 'SUCCESS' ? 'text-finance-success' :
                              log.status === 'FAILED' ? 'text-finance-danger' :
                              log.status === 'WARNING' ? 'text-finance-accent' : 'text-sky-400'
                            }`}>
                              [{log.stage}]
                            </span>{' '}
                            <span className="text-slate-200">{log.message}</span>
                            {log.duration > 0 && (
                              <span className="text-slate-500 text-[10px] ml-2">({log.duration.toFixed(2)}s)</span>
                            )}
                            {log.error && (
                              <pre className="text-red-400 mt-2 bg-red-950/20 p-2 rounded overflow-x-auto text-[10px] leading-tight max-w-full">
                                {log.error}
                              </pre>
                            )}
                          </div>
                        ))}
                        {(!selectedJob.logs || selectedJob.logs.length === 0) && (
                          <div className="text-slate-600 italic">No logs available for this job yet.</div>
                        )}
                        <div ref={logEndRef} />
                      </div>
                    </div>

                    {selectedJob.status === 'COMPLETED' && selectedJob.is_test && (
                      <div className="mt-4 border-t border-yellow-500/10 pt-4 space-y-3">
                        <h4 className="text-xs font-bold text-finance-accent uppercase tracking-wider">Test Video Preview</h4>
                        <div className="flex flex-col sm:flex-row gap-4 items-start">
                          <video 
                            src={`${API_BASE}/api/jobs/${selectedJob.id}/video`} 
                            controls 
                            className="w-full max-w-[140px] aspect-[9/16] bg-black rounded-xl border border-yellow-500/15 shadow-lg shadow-black/40"
                          />
                          <div className="space-y-3">
                            <p className="text-xs text-finance-textMuted max-w-xs leading-normal">
                              The test video is compiled locally on the backend. You can review font scaling, captions synchronization, charts, and voice pitch in this preview.
                            </p>
                            <a 
                              href={`${API_BASE}/api/jobs/${selectedJob.id}/video`}
                              download={`short_${selectedJob.id}.mp4`}
                              className="inline-flex items-center gap-2 px-4 py-2 bg-finance-accent hover:bg-yellow-500 text-finance-dark font-bold text-xs rounded-xl shadow transition-all active:scale-95"
                            >
                              Download Video file
                            </a>
                          </div>
                        </div>
                      </div>
                    )}

                    {selectedJob.error_message && (
                      <div className="bg-red-950/30 border border-red-500/20 p-4 rounded-xl mt-4 flex gap-2.5 text-xs text-red-300">
                        <AlertCircle className="w-5 h-5 shrink-0 text-red-400" />
                        <div>
                          <span className="font-bold">Execution Error:</span>
                          <p className="mt-0.5">{selectedJob.error_message}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-finance-textMuted py-20 text-center">
                    <Activity className="w-12 h-12 text-slate-700 mb-4" />
                    <span className="font-bold text-sm">Select a job from the panel</span>
                    <p className="text-xs mt-1 max-w-xs">Select a daily job on the left panel to review its timeline logs and progress stages.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="space-y-8">
            <div>
              <h1 className="text-3xl font-extrabold text-white">System Settings</h1>
              <p className="text-sm text-finance-textMuted mt-1">Configure Gemini API parameters, adjust voices, and manage system limits.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Gemini configuration */}
              <div className="glass-panel p-6 rounded-2xl border border-yellow-500/10 space-y-6">
                <h3 className="font-bold text-white text-base border-b border-yellow-500/10 pb-3">AI Settings (Gemini)</h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-finance-text uppercase tracking-wider mb-2">Gemini API Key</label>
                    <input 
                      type="password" 
                      value={newGeminiKey}
                      onChange={(e) => setNewGeminiKey(e.target.value)}
                      className="w-full px-4 py-2.5 bg-finance-dark/50 border border-yellow-500/20 focus:border-finance-accent/60 outline-none rounded-xl text-white placeholder-slate-600 transition-colors"
                      placeholder="Replace Gemini API Key..."
                    />
                    <p className="text-[10px] text-finance-textMuted mt-1">The key is encrypted at rest in database storage and never returned in plaintext.</p>
                  </div>

                  {geminiTestResult && (
                    <div className={`text-xs font-semibold px-3 py-2 rounded-lg inline-block ${
                      geminiTestResult.includes('Valid') 
                        ? 'bg-green-950/40 text-finance-success border border-green-500/20' 
                        : 'bg-red-950/40 text-finance-danger border border-red-500/20'
                    }`}>
                      {geminiTestResult}
                    </div>
                  )}

                  <div className="flex gap-4 pt-2">
                    <button
                      onClick={testGeminiKey}
                      disabled={!newGeminiKey}
                      className="px-4 py-2.5 bg-zinc-800 text-finance-text hover:bg-zinc-700 disabled:opacity-50 text-xs font-bold rounded-xl transition-all"
                    >
                      Test Key
                    </button>
                    <button
                      onClick={saveGeminiKey}
                      disabled={!newGeminiKey}
                      className="px-4 py-2.5 bg-finance-accent hover:bg-yellow-500 text-finance-dark disabled:opacity-50 text-xs font-bold rounded-xl transition-all shadow shadow-yellow-500/10"
                    >
                      Save Key
                    </button>
                  </div>
                </div>
              </div>

              {/* Other settings */}
              <div className="glass-panel p-6 rounded-2xl border border-yellow-500/10">
                <h3 className="font-bold text-white text-base border-b border-yellow-500/10 pb-3 mb-6">Pipeline Configurations</h3>
                
                <form onSubmit={updateAppSettings} className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[10px] font-bold text-finance-text uppercase tracking-wider mb-2">Daily Video Time</label>
                      <input 
                        type="text" 
                        value={settingsForm.daily_video_time}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, daily_video_time: e.target.value }))}
                        className="w-full px-4 py-2 bg-finance-dark/50 border border-yellow-500/15 rounded-xl text-white outline-none focus:border-finance-accent/40 text-sm"
                        placeholder="11:00 AM"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-finance-text uppercase tracking-wider mb-2">Videos Per Day</label>
                      <input 
                        type="number" 
                        value={settingsForm.videos_per_day}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, videos_per_day: parseInt(e.target.value) || 1 }))}
                        className="w-full px-4 py-2 bg-finance-dark/50 border border-yellow-500/15 rounded-xl text-white outline-none focus:border-finance-accent/40 text-sm"
                        min="1"
                        max="1"
                        disabled
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[10px] font-bold text-finance-text uppercase tracking-wider mb-2">Target Duration</label>
                      <input 
                        type="text" 
                        value={settingsForm.target_duration}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, target_duration: e.target.value }))}
                        className="w-full px-4 py-2 bg-finance-dark/50 border border-yellow-500/15 rounded-xl text-white outline-none focus:border-finance-accent/40 text-sm"
                        placeholder="30-60 sec"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-finance-text uppercase tracking-wider mb-2">Default TTS Voice</label>
                      <select 
                        value={settingsForm.default_tts_voice}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, default_tts_voice: e.target.value }))}
                        className="w-full px-4 py-2 bg-finance-dark/50 border border-yellow-500/15 rounded-xl text-white outline-none focus:border-finance-accent/40 text-sm"
                      >
                        <option value="en-IN-Wavenet-C">en-IN-Wavenet-C (Female)</option>
                        <option value="en-IN-Wavenet-B">en-IN-Wavenet-B (Male)</option>
                        <option value="en-IN-Neural2-B">en-IN-Neural2-B (Male)</option>
                        <option value="en-US-Wavenet-D">en-US-Wavenet-D (US Accent)</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[10px] font-bold text-finance-text uppercase tracking-wider mb-2">Min News Score</label>
                      <input 
                        type="number" 
                        value={settingsForm.minimum_news_score}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, minimum_news_score: parseInt(e.target.value) || 70 }))}
                        className="w-full px-4 py-2 bg-finance-dark/50 border border-yellow-500/15 rounded-xl text-white outline-none focus:border-finance-accent/40 text-sm"
                        min="50"
                        max="90"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-bold text-finance-text uppercase tracking-wider mb-2">YouTube Privacy</label>
                      <select 
                        value={settingsForm.youtube_privacy}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, youtube_privacy: e.target.value }))}
                        className="w-full px-4 py-2 bg-finance-dark/50 border border-yellow-500/15 rounded-xl text-white outline-none focus:border-finance-accent/40 text-sm"
                      >
                        <option value="public">Public</option>
                        <option value="private">Private</option>
                        <option value="unlisted">Unlisted</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex gap-6">
                    <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold">
                      <input 
                        type="checkbox" 
                        checked={settingsForm.auto_upload}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, auto_upload: e.target.checked }))}
                        className="rounded border-zinc-700 bg-zinc-950 accent-yellow-500 w-4 h-4"
                      />
                      Auto YouTube Upload
                    </label>
                    
                    <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold">
                      <input 
                        type="checkbox" 
                        checked={settingsForm.auto_voice}
                        onChange={(e) => setSettingsForm(prev => ({ ...prev, auto_voice: e.target.checked }))}
                        className="rounded border-zinc-700 bg-zinc-950 accent-yellow-500 w-4 h-4"
                      />
                      Auto Voice Narration
                    </label>
                  </div>

                  {settingsUpdateMsg && (
                    <div className="text-xs text-finance-success font-semibold">{settingsUpdateMsg}</div>
                  )}

                  <button
                    type="submit"
                    className="px-6 py-2.5 bg-finance-accent hover:bg-yellow-500 text-finance-dark font-bold text-xs rounded-xl transition-all shadow shadow-yellow-500/10 active:scale-95"
                  >
                    Update Configs
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
