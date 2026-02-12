import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Play, Clock, CheckCircle, XCircle, RefreshCw, Mail, Bell, Activity } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

function JobCard({ job, onRun, onPreview, running }) {
  const isReminder = job.id === "appointment_reminders";
  const Icon = isReminder ? Bell : Mail;
  const color = isReminder ? "#3b82f6" : "#D4AF37";

  return (
    <div data-testid={`job-card-${job.id}`} className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg" style={{ backgroundColor: `${color}15` }}>
            <Icon size={20} style={{ color }} />
          </div>
          <div>
            <h3 className="text-zinc-100 font-semibold text-sm">{job.name}</h3>
            <p className="text-zinc-500 text-xs mt-0.5">{job.trigger}</p>
          </div>
        </div>
        <span className="text-xs px-2 py-1 rounded-full bg-green-500/15 text-green-400">Active</span>
      </div>

      <div className="flex items-center gap-2 text-xs text-zinc-400 mb-4">
        <Clock size={12} />
        <span>Next run: {job.next_run ? new Date(job.next_run).toLocaleString() : "N/A"}</span>
      </div>

      <div className="flex gap-2">
        <button
          data-testid={`run-${job.id}`}
          onClick={onRun}
          disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 transition-colors disabled:opacity-50"
        >
          {running ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
          {running ? "Running..." : "Run Now"}
        </button>
        <button
          data-testid={`preview-${job.id}`}
          onClick={onPreview}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
        >
          Preview
        </button>
      </div>
    </div>
  );
}

function ResultModal({ title, data, onClose }) {
  if (!data) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div data-testid="job-result-modal" className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-zinc-100 font-semibold">{title}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200">&times;</button>
        </div>
        <pre className="text-xs text-zinc-300 bg-zinc-950 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    </div>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runningJob, setRunningJob] = useState(null);
  const [modal, setModal] = useState(null);

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statusRes, historyRes] = await Promise.all([
        axios.get(`${API}/jobs/status`),
        axios.get(`${API}/reporting/jobs-history?limit=20`),
      ]);
      setJobs(statusRes.data.jobs || []);
      setHistory(historyRes.data.entries || []);
    } catch (e) {
      console.error("Failed to load jobs", e);
    }
    setLoading(false);
  };

  const runJob = async (jobId) => {
    setRunningJob(jobId);
    try {
      const endpoint = jobId === "appointment_reminders" ? "/jobs/reminders/run" : "/jobs/daily-summary/run";
      const res = await axios.post(`${API}${endpoint}`);
      setModal({ title: `Run Result: ${jobId}`, data: res.data });
      fetchAll();
    } catch (e) {
      setModal({ title: "Error", data: { error: e.message } });
    }
    setRunningJob(null);
  };

  const previewJob = async (jobId) => {
    try {
      const endpoint = jobId === "appointment_reminders" ? "/jobs/reminders/preview" : "/jobs/daily-summary/preview";
      const res = await axios.get(`${API}${endpoint}`);
      setModal({ title: `Preview: ${jobId}`, data: res.data });
    } catch (e) {
      setModal({ title: "Error", data: { error: e.message } });
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div data-testid="jobs-page" className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Background Jobs</h1>
            <p className="text-zinc-500 text-sm mt-1">Scheduled tasks & automation</p>
          </div>
          <button
            data-testid="refresh-jobs"
            onClick={fetchAll}
            className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {/* Status Banner */}
        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4 flex items-center gap-3">
          <Activity size={18} className="text-green-400" />
          <div>
            <span className="text-green-400 font-medium text-sm">Scheduler Running</span>
            <span className="text-zinc-400 text-sm ml-3">{jobs.length} active jobs</span>
          </div>
        </div>

        {/* Job Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onRun={() => runJob(job.id)}
              onPreview={() => previewJob(job.id)}
              running={runningJob === job.id}
            />
          ))}
        </div>

        {/* Execution History */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg">
          <div className="p-5 border-b border-zinc-800">
            <h3 className="text-zinc-200 font-semibold">Execution History</h3>
            <p className="text-zinc-500 text-xs mt-1">Recent audit log entries for scheduled tasks</p>
          </div>
          <div className="divide-y divide-zinc-800 max-h-96 overflow-y-auto">
            {history.length > 0 ? history.map((entry, i) => (
              <div key={i} data-testid={`history-entry-${i}`} className="px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {entry.success ? (
                    <CheckCircle size={14} className="text-green-400" />
                  ) : (
                    <XCircle size={14} className="text-red-400" />
                  )}
                  <div>
                    <span className="text-zinc-200 text-sm">{entry.action?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                    <span className="text-zinc-600 text-xs ml-2">via {entry.provider}</span>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${entry.success ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"}`}>
                    {entry.success ? "Success" : "Failed"}
                  </span>
                  <div className="text-zinc-600 text-xs mt-0.5">
                    {entry.created_at ? new Date(entry.created_at).toLocaleString() : "N/A"}
                  </div>
                </div>
              </div>
            )) : (
              <div className="px-5 py-8 text-center text-zinc-500 text-sm">
                No execution history yet. Run a job to see results here.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Result Modal */}
      <ResultModal
        title={modal?.title}
        data={modal?.data}
        onClose={() => setModal(null)}
      />
    </Layout>
  );
}
