import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../components/ui/alert-dialog";
import { toast } from "sonner";
import {
  Users,
  Clock,
  Scissors,
  Phone,
  User,
  Plus,
  Play,
  CheckCircle,
  XCircle,
  Timer,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const statusColors = {
  waiting: "bg-yellow-500/20 text-yellow-400",
  notified: "bg-blue-500/20 text-blue-400",
  serving: "bg-emerald-500/20 text-emerald-400",
  completed: "bg-zinc-500/20 text-zinc-400",
  left: "bg-red-500/20 text-red-400",
};

export default function WalkInQueuePage() {
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [clients, setClients] = useState([]);
  const [services, setServices] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [form, setForm] = useState({ client_id: "", service_id: "", barber_id: "" });
  const intervalRef = useRef(null);

  useEffect(() => {
    fetchQueue();
    fetchStats();
    // Auto-refresh every 10 seconds
    intervalRef.current = setInterval(() => {
      fetchQueue();
      fetchStats();
    }, 10000);
    return () => clearInterval(intervalRef.current);
  }, []);

  const fetchQueue = async () => {
    try {
      const response = await axios.get(`${API}/walkin-queue?include_completed=true`);
      setQueue(response.data.queue || []);
    } catch (error) {
      console.error("Failed to fetch queue:", error);
      if (loading) toast.error("Failed to load walk-in queue");
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/walkin-queue/stats`);
      setStats(response.data);
    } catch {
      // Non-critical
    }
  };

  const fetchFormData = async () => {
    try {
      const [c, s, b] = await Promise.all([
        axios.get(`${API}/clients?limit=200`),
        axios.get(`${API}/services`),
        axios.get(`${API}/barbers`),
      ]);
      setClients(c.data.clients || []);
      setServices(s.data.services || []);
      setBarbers(b.data.barbers || []);
    } catch {
      toast.error("Failed to load form data");
    }
  };

  const openDialog = () => {
    fetchFormData();
    setForm({ client_id: "", service_id: "", barber_id: "" });
    setDialogOpen(true);
  };

  const handleCreate = async () => {
    if (!form.client_id) {
      toast.error("Client is required");
      return;
    }
    setCreating(true);
    try {
      await axios.post(`${API}/walkin-queue`, form);
      toast.success("Added to walk-in queue");
      setDialogOpen(false);
      fetchQueue();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add to queue");
    } finally {
      setCreating(false);
    }
  };

  const updateStatus = async (entryId, newStatus, barberId) => {
    try {
      const params = new URLSearchParams({ status: newStatus });
      if (barberId) params.append("assigned_barber_id", barberId);
      await axios.patch(`${API}/walkin-queue/${entryId}/status?${params}`);
      toast.success(`Status updated to ${newStatus}`);
      fetchQueue();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update status");
    }
  };

  const removeEntry = async (entryId) => {
    try {
      await axios.delete(`${API}/walkin-queue/${entryId}`);
      toast.success("Removed from queue");
      fetchQueue();
      fetchStats();
    } catch (error) {
      toast.error("Failed to remove from queue");
    }
  };

  const activeQueue = queue.filter((e) => ["waiting", "notified", "serving"].includes(e.status));
  const completedToday = queue.filter((e) => e.status === "completed");

  if (loading) {
    return (
      <Layout title="Walk-in Queue">
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="bg-card border-border animate-pulse">
                <CardContent className="p-4"><div className="h-16 bg-muted rounded" /></CardContent>
              </Card>
            ))}
          </div>
          <Card className="bg-card border-border animate-pulse">
            <CardContent className="p-6"><div className="h-40 bg-muted rounded" /></CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Walk-in Queue">
      <div data-testid="walkin-queue-page" className="space-y-6">
        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
                  <Users className="w-5 h-5 text-yellow-400" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">In Queue</p>
                  <p className="font-mono font-medium text-2xl">{stats?.current_queue_size ?? 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <Scissors className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Serving</p>
                  <p className="font-mono font-medium text-2xl">{stats?.currently_serving ?? 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <CheckCircle className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Served Today</p>
                  <p className="font-mono font-medium text-2xl">{stats?.served_today ?? 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Timer className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Avg Wait</p>
                  <p className="font-mono font-medium text-2xl">{stats?.avg_wait_today ?? 0}<span className="text-sm text-muted-foreground ml-1">min</span></p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Header */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Users className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-heading text-xl font-semibold">Live Queue</h3>
                  <p className="text-muted-foreground text-sm">
                    {activeQueue.length} {activeQueue.length === 1 ? "person" : "people"} in queue
                    <span className="text-xs ml-2 text-muted-foreground/60">Auto-refreshes every 10s</span>
                  </p>
                </div>
              </div>
              <Button onClick={openDialog} data-testid="add-walkin-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Walk-in
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Add Walk-in Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Add Walk-in</DialogTitle>
              <DialogDescription>Add a client to the walk-in queue.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>Client *</Label>
                <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                  <SelectTrigger data-testid="wq-client-select"><SelectValue placeholder="Select client" /></SelectTrigger>
                  <SelectContent>
                    {clients.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name} ({c.phone})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Service (optional)</Label>
                <Select value={form.service_id} onValueChange={(v) => setForm({ ...form, service_id: v })}>
                  <SelectTrigger><SelectValue placeholder="Any service" /></SelectTrigger>
                  <SelectContent>
                    {services.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name} (${s.price})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Preferred Barber (optional)</Label>
                <Select value={form.barber_id} onValueChange={(v) => setForm({ ...form, barber_id: v })}>
                  <SelectTrigger><SelectValue placeholder="Any barber" /></SelectTrigger>
                  <SelectContent>
                    {barbers.map((b) => (
                      <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={creating} data-testid="submit-walkin-btn">
                {creating ? "Adding..." : "Add to Queue"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Active Queue Table */}
        <Card className="bg-card border-border">
          <CardHeader className="border-b border-border">
            <CardTitle className="font-heading text-lg">Active Queue</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground w-16">#</TableHead>
                  <TableHead className="text-muted-foreground">Client</TableHead>
                  <TableHead className="text-muted-foreground">Service</TableHead>
                  <TableHead className="text-muted-foreground">Barber</TableHead>
                  <TableHead className="text-muted-foreground">Wait Time</TableHead>
                  <TableHead className="text-muted-foreground">Status</TableHead>
                  <TableHead className="text-muted-foreground">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeQueue.length === 0 ? (
                  <TableRow className="border-border">
                    <TableCell colSpan={7} className="text-center py-12">
                      <div className="text-muted-foreground">
                        <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg">No one in the queue</p>
                        <p className="text-sm">Walk-in clients will appear here when they join</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  activeQueue.map((entry) => (
                    <TableRow
                      key={entry.id}
                      className={`border-border hover:bg-accent/30 ${entry.status === "notified" ? "bg-blue-500/5" : ""}`}
                      data-testid={`queue-row-${entry.id}`}
                    >
                      <TableCell>
                        <span className="font-mono font-bold text-lg text-primary">
                          {entry.status === "serving" ? "" : entry.position}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center">
                            <User className="w-4 h-4 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="font-medium">{entry.client?.name || "Unknown"}</p>
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Phone className="w-3 h-3" />
                              {entry.client?.phone}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        {entry.service ? (
                          <div className="flex items-center gap-2">
                            <Scissors className="w-4 h-4 text-muted-foreground" />
                            {entry.service.name}
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">Any</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {entry.assigned_barber?.name || entry.barber?.name || (
                          <span className="text-muted-foreground text-sm">Any</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="text-sm">
                            {formatDistanceToNow(new Date(entry.joined_at), { addSuffix: false })}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={statusColors[entry.status] || "bg-secondary"}>
                          {entry.status === "notified" ? "Next up" : entry.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {entry.status !== "serving" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                              onClick={() => updateStatus(entry.id, "serving")}
                              data-testid={`serve-${entry.id}`}
                            >
                              <Play className="w-4 h-4 mr-1" />
                              Serve
                            </Button>
                          )}
                          {entry.status === "serving" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                              onClick={() => updateStatus(entry.id, "completed")}
                              data-testid={`complete-${entry.id}`}
                            >
                              <CheckCircle className="w-4 h-4 mr-1" />
                              Done
                            </Button>
                          )}
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="text-muted-foreground hover:text-destructive"
                                data-testid={`remove-queue-${entry.id}`}
                              >
                                <XCircle className="w-4 h-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Remove from Queue?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This will remove {entry.client?.name || "this client"} from the walk-in queue.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => removeEntry(entry.id)}
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                >
                                  Remove
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Completed Today */}
        {completedToday.length > 0 && (
          <Card className="bg-card border-border">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-heading text-lg text-muted-foreground">
                Completed Today ({completedToday.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-muted-foreground">Client</TableHead>
                    <TableHead className="text-muted-foreground">Service</TableHead>
                    <TableHead className="text-muted-foreground">Barber</TableHead>
                    <TableHead className="text-muted-foreground">Wait Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {completedToday.map((entry) => {
                    let waitMin = "";
                    if (entry.joined_at && entry.serving_at) {
                      const diff = (new Date(entry.serving_at) - new Date(entry.joined_at)) / 60000;
                      waitMin = `${Math.round(diff)} min`;
                    }
                    return (
                      <TableRow key={entry.id} className="border-border opacity-60">
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <User className="w-4 h-4 text-muted-foreground" />
                            {entry.client?.name || "Unknown"}
                          </div>
                        </TableCell>
                        <TableCell>{entry.service?.name || "N/A"}</TableCell>
                        <TableCell>{entry.assigned_barber?.name || entry.barber?.name || "N/A"}</TableCell>
                        <TableCell className="font-mono text-sm">{waitMin || "N/A"}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {/* Info Card */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center shrink-0">
                <Clock className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h4 className="font-medium mb-1">How Walk-in Queue Works</h4>
                <p className="text-sm text-muted-foreground">
                  Clients can text <span className="font-mono text-primary">WAIT</span> to join the queue via SMS,
                  or you can add them manually. They receive their position and estimated wait time.
                  When they're next in line, they get a "you're next" notification automatically.
                  Use <span className="font-mono text-primary">QSTATUS</span> to check position
                  and <span className="font-mono text-primary">LEAVE</span> to exit.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
