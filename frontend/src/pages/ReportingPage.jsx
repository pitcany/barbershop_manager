import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { TrendingUp, DollarSign, AlertTriangle, Users, ArrowUpRight, Calendar, MessageSquare, Activity } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const COLORS = ["#D4AF37", "#22c55e", "#ef4444", "#3b82f6", "#a855f7", "#f59e0b"];

function StatCard({ icon: Icon, label, value, sub, color = "#D4AF37" }) {
  return (
    <div data-testid={`stat-${label.toLowerCase().replace(/\s+/g, '-')}`} className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-zinc-400 text-sm">{label}</span>
        <Icon size={18} style={{ color }} />
      </div>
      <div className="text-2xl font-bold text-zinc-100">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function ReportingPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    fetchData();
  }, [days]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/reporting/overview?days=${days}`);
      setData(res.data);
    } catch (e) {
      console.error("Failed to load reporting data", e);
    }
    setLoading(false);
  };

  if (loading || !data) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-amber-500" />
        </div>
      </Layout>
    );
  }

  const { appointments, revenue, daily_trend, recovered_events, barber_performance, messages } = data;

  const statusData = Object.entries(appointments.by_status || {}).map(([status, info]) => ({
    name: status.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase()),
    value: info.count,
    revenue: info.revenue,
  }));

  const recoveredSourceData = Object.entries(revenue.recovered_by_source || {}).map(([source, info]) => ({
    name: source.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase()),
    amount: info.amount,
    count: info.count,
  }));

  return (
    <Layout>
      <div data-testid="reporting-page" className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Reporting</h1>
            <p className="text-zinc-500 text-sm mt-1">Revenue & operations analytics</p>
          </div>
          <select
            data-testid="period-select"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="bg-zinc-900 border border-zinc-700 text-zinc-200 rounded-lg px-3 py-2 text-sm"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={Calendar}
            label="Total Appointments"
            value={appointments.total}
            sub={`${days}-day period`}
          />
          <StatCard
            icon={DollarSign}
            label="Revenue Earned"
            value={`$${(revenue.total_earned || 0).toFixed(2)}`}
            sub="From completed appointments"
            color="#22c55e"
          />
          <StatCard
            icon={TrendingUp}
            label="Revenue Recovered"
            value={`$${(revenue.total_recovered || 0).toFixed(2)}`}
            sub="Waitlist fills + no-show fees"
            color="#D4AF37"
          />
          <StatCard
            icon={AlertTriangle}
            label="No-Show Rate"
            value={`${appointments.no_show_rate}%`}
            sub={`${appointments.by_status?.no_show?.count || 0} no-shows`}
            color="#ef4444"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Daily Trend */}
          <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-lg p-5">
            <h3 className="text-zinc-200 font-semibold mb-4">Daily Appointment Trend</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={daily_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fill: "#71717a", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: 8 }}
                  labelStyle={{ color: "#fafafa" }}
                />
                <Legend />
                <Bar dataKey="completed" fill="#22c55e" name="Completed" radius={[2, 2, 0, 0]} />
                <Bar dataKey="no_shows" fill="#ef4444" name="No-Shows" radius={[2, 2, 0, 0]} />
                <Bar dataKey="cancelled" fill="#f59e0b" name="Cancelled" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Status Breakdown */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
            <h3 className="text-zinc-200 font-semibold mb-4">Status Breakdown</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={statusData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {statusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-3 space-y-1">
              {statusData.map((s, i) => (
                <div key={s.name} className="flex justify-between text-xs">
                  <span className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                    <span className="text-zinc-400">{s.name}</span>
                  </span>
                  <span className="text-zinc-300">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Revenue & Barbers Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Revenue Chart */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
            <h3 className="text-zinc-200 font-semibold mb-4">Daily Revenue</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={daily_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fill: "#71717a", fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: 8 }}
                  formatter={(v) => [`$${v.toFixed(2)}`]}
                />
                <Line type="monotone" dataKey="revenue" stroke="#D4AF37" strokeWidth={2} dot={{ fill: "#D4AF37", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Barber Performance */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
            <h3 className="text-zinc-200 font-semibold mb-4">Barber Performance</h3>
            {barber_performance.length > 0 ? (
              <div className="space-y-3">
                {barber_performance.map((b, i) => {
                  const completionRate = b.total > 0 ? Math.round((b.completed / b.total) * 100) : 0;
                  return (
                    <div key={i} data-testid={`barber-stat-${i}`} className="bg-zinc-800/50 rounded-lg p-3">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-zinc-200 font-medium text-sm">{b.name}</span>
                        <span className="text-amber-500 text-sm font-semibold">${(b.revenue || 0).toFixed(0)}</span>
                      </div>
                      <div className="flex gap-4 text-xs text-zinc-400">
                        <span>{b.total} appts</span>
                        <span className="text-green-400">{b.completed} done</span>
                        <span className="text-red-400">{b.no_shows} no-show</span>
                      </div>
                      <div className="mt-2 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${completionRate}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-zinc-500 text-sm">No barber data for this period</p>
            )}
          </div>
        </div>

        {/* Activity & Recovered Revenue */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Messages & Activity */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
            <h3 className="text-zinc-200 font-semibold mb-4 flex items-center gap-2">
              <MessageSquare size={16} /> Message Activity
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-800/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-zinc-100">{messages.inbound || 0}</div>
                <div className="text-xs text-zinc-400 mt-1">Inbound</div>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-zinc-100">{messages.outbound || 0}</div>
                <div className="text-xs text-zinc-400 mt-1">Outbound</div>
              </div>
            </div>

            {/* Recovered Sources */}
            <h4 className="text-zinc-300 font-medium mt-5 mb-3 text-sm">Recovered Revenue Sources</h4>
            {recoveredSourceData.length > 0 ? (
              <div className="space-y-2">
                {recoveredSourceData.map((s, i) => (
                  <div key={i} className="flex justify-between items-center bg-zinc-800/50 rounded p-3">
                    <span className="text-zinc-300 text-sm">{s.name}</span>
                    <div className="text-right">
                      <span className="text-green-400 font-semibold text-sm">${s.amount.toFixed(2)}</span>
                      <span className="text-zinc-500 text-xs ml-2">({s.count} events)</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-zinc-500 text-sm">No recovered revenue in this period</p>
            )}
          </div>

          {/* Recent Recovery Events */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
            <h3 className="text-zinc-200 font-semibold mb-4 flex items-center gap-2">
              <ArrowUpRight size={16} className="text-green-400" /> Recent Recovery Events
            </h3>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {recovered_events.length > 0 ? recovered_events.map((evt, i) => (
                <div key={i} data-testid={`recovery-event-${i}`} className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-3">
                  <div className="flex justify-between items-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      evt.source === "waitlist_fill" ? "bg-blue-500/20 text-blue-400" : "bg-amber-500/20 text-amber-400"
                    }`}>
                      {evt.source.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase())}
                    </span>
                    <span className="text-green-400 font-semibold text-sm">${(evt.amount || 0).toFixed(2)}</span>
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {new Date(evt.attributed_at).toLocaleDateString()} &middot; {evt.notes || "No notes"}
                  </div>
                </div>
              )) : (
                <p className="text-zinc-500 text-sm">No recovery events in this period</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
