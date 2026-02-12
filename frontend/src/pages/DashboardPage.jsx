import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import {
  Calendar,
  DollarSign,
  Users,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock
} from "lucide-react";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from "recharts";

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

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, chartRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`),
        axios.get(`${API}/dashboard/revenue-chart?days=14`)
      ]);
      setStats(statsRes.data);
      setChartData(fillDateGaps(chartRes.data.data, 14));
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Dashboard">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="bg-card border-border animate-pulse">
              <CardContent className="p-6">
                <div className="h-20 bg-muted rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      </Layout>
    );
  }

  const statCards = [
    {
      title: "Today's Appointments",
      value: stats?.appointments_today || 0,
      icon: Calendar,
      color: "text-primary",
      bgColor: "bg-primary/10"
    },
    {
      title: "Revenue Recovered",
      value: `$${(stats?.revenue_recovered || 0).toFixed(2)}`,
      icon: TrendingUp,
      color: "text-emerald-400",
      bgColor: "bg-emerald-500/10",
      isMoney: true
    },
    {
      title: "No-Show Rate",
      value: `${stats?.no_show_rate || 0}%`,
      icon: AlertTriangle,
      color: stats?.no_show_rate > 10 ? "text-red-400" : "text-yellow-400",
      bgColor: stats?.no_show_rate > 10 ? "bg-red-500/10" : "bg-yellow-500/10"
    },
    {
      title: "Messages Today",
      value: stats?.messages_today || 0,
      icon: MessageSquare,
      color: "text-blue-400",
      bgColor: "bg-blue-500/10"
    }
  ];

  const secondaryStats = [
    {
      title: "Monthly Appointments",
      value: stats?.appointments_month || 0,
      icon: Calendar
    },
    {
      title: "No-Shows This Month",
      value: stats?.no_shows_month || 0,
      icon: TrendingDown
    },
    {
      title: "Waitlist",
      value: stats?.waitlist_count || 0,
      icon: Users
    },
    {
      title: "Deposits Collected",
      value: `$${(stats?.deposits_collected || 0).toFixed(2)}`,
      icon: DollarSign
    }
  ];

  return (
    <Layout title="Dashboard">
      <div data-testid="dashboard-page" className="space-y-8">
        {/* Main Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {statCards.map((stat, index) => (
            <Card 
              key={index} 
              className="bg-card border-border hover:border-primary/50 transition-colors duration-300"
              data-testid={`stat-card-${index}`}
            >
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">{stat.title}</p>
                    <p className={`font-mono font-medium text-2xl ${stat.isMoney ? 'text-emerald-400' : ''}`}>
                      {stat.value}
                    </p>
                  </div>
                  <div className={`w-12 h-12 rounded-lg ${stat.bgColor} flex items-center justify-center`}>
                    <stat.icon className={`w-6 h-6 ${stat.color}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

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
                  <XAxis 
                    dataKey="date" 
                    stroke="#a1a1aa"
                    tick={{ fill: '#a1a1aa', fontSize: 12 }}
                    tickFormatter={(value) => {
                      const date = new Date(value);
                      return `${date.getMonth() + 1}/${date.getDate()}`;
                    }}
                  />
                  <YAxis 
                    stroke="#a1a1aa"
                    tick={{ fill: '#a1a1aa', fontSize: 12 }}
                    tickFormatter={(value) => `$${value}`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#18181b', 
                      border: '1px solid #27272a',
                      borderRadius: '8px',
                      color: '#fafafa'
                    }}
                    formatter={(value) => [`$${value.toFixed(2)}`, '']}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="recovered" 
                    stroke="#10b981" 
                    fillOpacity={1}
                    fill="url(#colorRecovered)"
                    name="Recovered"
                  />
                  <Area 
                    type="monotone" 
                    dataKey="lost" 
                    stroke="#ef4444" 
                    fillOpacity={1}
                    fill="url(#colorLost)"
                    name="Lost"
                  />
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
