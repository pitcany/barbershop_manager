import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  Calendar,
  DollarSign,
  Users,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock,
  User,
  Scissors,
  Link2,
  Copy
} from "lucide-react";
import { 
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

const statusColors = {
  pending: "bg-yellow-500/20 text-yellow-400",
  confirmed: "bg-emerald-500/20 text-emerald-400",
  deposit_pending: "bg-orange-500/20 text-orange-400",
  deposit_paid: "bg-emerald-500/20 text-emerald-400",
  completed: "bg-blue-500/20 text-blue-400",
  no_show: "bg-red-500/20 text-red-400",
};

function fillDateGaps(data, days) {
  if (!data || data.length === 0) return data;
  const dataMap = {};
  data.forEach(d => { dataMap[d.date] = d; });
  const filled = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    filled.push(dataMap[dateStr] || { date: dateStr, recovered: 0, lost: 0 });
  }
  return filled;
}

function formatTime(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch { return ""; }
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [todaySchedule, setTodaySchedule] = useState([]);
  const [shopSlug, setShopSlug] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [statsRes, chartRes, scheduleRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`),
        axios.get(`${API}/dashboard/revenue-chart?days=14`),
        axios.get(`${API}/dashboard/today-schedule`),
      ]);
      setStats(statsRes.data);
      setChartData(fillDateGaps(chartRes.data.data, 14));
      setTodaySchedule(scheduleRes.data.appointments || []);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
    // Fetch shop slug separately so a failure doesn't break the dashboard
    try {
      const shopRes = await axios.get(`${API}/shop`);
      setShopSlug(shopRes.data.slug || "");
    } catch {
      // Non-critical — dashboard renders fine without the booking link slug
    }
  };

  if (loading) {
    return (
      <Layout title="Dashboard">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="bg-card border-border animate-pulse">
              <CardContent className="p-6"><div className="h-20 bg-muted rounded" /></CardContent>
            </Card>
          ))}
        </div>
      </Layout>
    );
  }

  const statCards = [
    { title: "Today's Appointments", value: stats?.today_appointments || 0, icon: Calendar, color: "text-primary", bgColor: "bg-primary/10" },
    { title: "Revenue Recovered", value: `$${(stats?.revenue_recovered || 0).toFixed(2)}`, icon: TrendingUp, color: "text-emerald-400", bgColor: "bg-emerald-500/10", isMoney: true },
    { title: "No-Show Rate", value: `${stats?.no_show_rate || 0}%`, icon: AlertTriangle, color: stats?.no_show_rate > 10 ? "text-red-400" : "text-yellow-400", bgColor: stats?.no_show_rate > 10 ? "bg-red-500/10" : "bg-yellow-500/10" },
    { title: "Messages Today", value: stats?.messages_today || 0, icon: MessageSquare, color: "text-blue-400", bgColor: "bg-blue-500/10" },
  ];

  const secondaryStats = [
    { title: "Monthly Appointments", value: stats?.appointments_month || 0, icon: Calendar },
    { title: "No-Shows This Month", value: stats?.no_shows_month || 0, icon: TrendingDown },
    { title: "Waitlist", value: stats?.waitlist_count || 0, icon: Users },
    { title: "Deposits Collected", value: `$${(stats?.deposits_collected || 0).toFixed(2)}`, icon: DollarSign },
  ];

  return (
    <Layout title="Dashboard">
      <div data-testid="dashboard-page" className="space-y-8">
        {/* Main Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {statCards.map((stat, index) => (
            <Card key={index} className="bg-card border-border hover:border-primary/50 transition-colors duration-300" data-testid={`stat-card-${index}`}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">{stat.title}</p>
                    <p className={`font-mono font-medium text-2xl ${stat.isMoney ? 'text-emerald-400' : ''}`}>{stat.value}</p>
                  </div>
                  <div className={`w-12 h-12 rounded-lg ${stat.bgColor} flex items-center justify-center`}>
                    <stat.icon className={`w-6 h-6 ${stat.color}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Booking Link Quick Action */}
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Link2 className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="text-sm font-medium">Online Booking Link</p>
                  <code className="text-xs text-muted-foreground font-mono">{window.location.origin}/book{shopSlug ? `/${shopSlug}` : ""}</code>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                data-testid="dashboard-copy-booking-link"
                className="gap-2"
                onClick={() => {
                  const link = `${window.location.origin}/book${shopSlug ? `/${shopSlug}` : ""}`;
                  navigator.clipboard.writeText(link)
                    .then(() => toast.success("Booking link copied!"))
                    .catch(() => toast.error("Failed to copy"));
                }}
              >
                <Copy className="w-3.5 h-3.5" /> Copy Link
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Today's Schedule */}
        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="font-heading text-xl flex items-center gap-2">
                <Clock className="w-5 h-5 text-primary" /> Today's Schedule
              </CardTitle>
              <Badge variant="outline" className="text-xs">{todaySchedule.length} appointment{todaySchedule.length !== 1 ? "s" : ""}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {todaySchedule.length === 0 ? (
              <p data-testid="no-schedule-msg" className="text-muted-foreground text-center py-8">No appointments scheduled for today.</p>
            ) : (
              <div data-testid="today-schedule" className="space-y-3">
                {todaySchedule.map((apt) => {
                  const isPast = new Date(apt.scheduled_at) < new Date();
                  return (
                    <div
                      key={apt.id}
                      data-testid={`schedule-item-${apt.id}`}
                      className={`flex items-center gap-4 p-3 rounded-lg border border-border ${isPast ? "opacity-60" : "hover:bg-accent/30"} transition-colors`}
                    >
                      <div className="w-16 text-center shrink-0">
                        <p className="font-mono font-semibold text-sm">{formatTime(apt.scheduled_at)}</p>
                        <p className="text-[10px] text-muted-foreground">{apt.duration_minutes}min</p>
                      </div>
                      <div className="w-px h-10 bg-border" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <User className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-medium text-sm truncate">{apt.client?.name || "Unknown"}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <Scissors className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="text-xs text-muted-foreground truncate">{apt.service?.name || "Unknown"}</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-xs text-muted-foreground">{apt.barber?.name || ""}</p>
                        <Badge className={`text-[10px] mt-1 ${statusColors[apt.status] || "bg-secondary"}`}>
                          {apt.status.replace(/_/g, " ")}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Revenue Chart */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="font-heading text-xl">Revenue Overview (14 Days)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72" data-testid="revenue-chart">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorLost" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="date" stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }}
                    tickFormatter={(v) => { const d = new Date(v); return `${d.getMonth()+1}/${d.getDate()}`; }} />
                  <YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', color: '#fafafa' }}
                    formatter={(v) => [`$${v.toFixed(2)}`, '']} labelFormatter={(l) => new Date(l).toLocaleDateString()} />
                  <Area type="monotone" dataKey="recovered" stroke="#10b981" fillOpacity={1} fill="url(#colorRecovered)" name="Recovered" />
                  <Area type="monotone" dataKey="lost" stroke="#ef4444" fillOpacity={1} fill="url(#colorLost)" name="Lost" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-8 mt-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-emerald-500 rounded-full" />
                <span className="text-sm text-muted-foreground">Revenue Recovered</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full" />
                <span className="text-sm text-muted-foreground">Revenue Lost (No-Shows)</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Secondary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {secondaryStats.map((stat, index) => (
            <Card key={index} className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <stat.icon className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">{stat.title}</p>
                    <p className="font-mono font-medium">{stat.value}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </Layout>
  );
}
