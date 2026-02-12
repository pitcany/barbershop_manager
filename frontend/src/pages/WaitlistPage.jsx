import { useState, useEffect } from "react";
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
  Calendar,
  Scissors,
  Phone,
  Trash2,
  User,
  Plus,
} from "lucide-react";
import { format } from "date-fns";

export default function WaitlistPage() {
  const [waitlist, setWaitlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [clients, setClients] = useState([]);
  const [services, setServices] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [form, setForm] = useState({
    client_id: "",
    service_id: "",
    barber_id: "",
    preferred_date: "",
    flexible_hours: 2,
  });

  useEffect(() => {
    fetchWaitlist();
  }, []);

  const fetchWaitlist = async () => {
    try {
      const response = await axios.get(`${API}/waitlist`);
      setWaitlist(response.data.waitlist);
    } catch (error) {
      console.error("Failed to fetch waitlist:", error);
      toast.error("Failed to load waitlist");
    } finally {
      setLoading(false);
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
    setForm({ client_id: "", service_id: "", barber_id: "", preferred_date: "", flexible_hours: 2 });
    setDialogOpen(true);
  };

  const handleCreate = async () => {
    if (!form.client_id || !form.service_id || !form.preferred_date) {
      toast.error("Client, service, and preferred date are required");
      return;
    }
    setCreating(true);
    try {
      await axios.post(`${API}/waitlist`, {
        ...form,
        preferred_date: new Date(form.preferred_date).toISOString(),
      });
      toast.success("Added to waitlist");
      setDialogOpen(false);
      fetchWaitlist();
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail || "Failed to add to waitlist");
    } finally {
      setCreating(false);
    }
  };

  const removeFromWaitlist = async (entryId) => {
    try {
      await axios.delete(`${API}/waitlist/${entryId}`);
      toast.success("Removed from waitlist");
      fetchWaitlist();
    } catch (error) {
      toast.error("Failed to remove from waitlist");
    }
  };

  return (
    <Layout title="Waitlist">
      <div data-testid="waitlist-page" className="space-y-6">
        {/* Summary Card */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Users className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-heading text-xl font-semibold">Active Waitlist</h3>
                  <p className="text-muted-foreground">
                    {waitlist.length} {waitlist.length === 1 ? "client" : "clients"} waiting for slots
                  </p>
                </div>
              </div>
              <Button onClick={openDialog} data-testid="add-waitlist-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add to Waitlist
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Add to Waitlist Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Add to Waitlist</DialogTitle>
              <DialogDescription>Add a client to the waitlist for an available slot.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>Client *</Label>
                <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                  <SelectTrigger data-testid="wl-client-select"><SelectValue placeholder="Select client" /></SelectTrigger>
                  <SelectContent>
                    {clients.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name} ({c.phone})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Service *</Label>
                <Select value={form.service_id} onValueChange={(v) => setForm({ ...form, service_id: v })}>
                  <SelectTrigger data-testid="wl-service-select"><SelectValue placeholder="Select service" /></SelectTrigger>
                  <SelectContent>
                    {services.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Preferred Barber</Label>
                <Select value={form.barber_id} onValueChange={(v) => setForm({ ...form, barber_id: v })}>
                  <SelectTrigger><SelectValue placeholder="Any barber" /></SelectTrigger>
                  <SelectContent>
                    {barbers.map((b) => (
                      <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Preferred Date *</Label>
                <Input
                  type="datetime-local"
                  value={form.preferred_date}
                  onChange={(e) => setForm({ ...form, preferred_date: e.target.value })}
                  data-testid="wl-date-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Flexibility (hours)</Label>
                <Input
                  type="number"
                  min={0}
                  value={form.flexible_hours}
                  onChange={(e) => setForm({ ...form, flexible_hours: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={creating} data-testid="submit-waitlist-btn">
                {creating ? "Adding..." : "Add"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Waitlist Table */}
        <Card className="bg-card border-border">
          <CardHeader className="border-b border-border">
            <CardTitle className="font-heading text-lg">Waitlist Entries</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">Client</TableHead>
                  <TableHead className="text-muted-foreground">Service</TableHead>
                  <TableHead className="text-muted-foreground">Preferred Date</TableHead>
                  <TableHead className="text-muted-foreground">Flexibility</TableHead>
                  <TableHead className="text-muted-foreground">Contact Attempts</TableHead>
                  <TableHead className="text-muted-foreground">Added</TableHead>
                  <TableHead className="text-muted-foreground">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(3)].map((_, i) => (
                    <TableRow key={i} className="border-border">
                      <TableCell colSpan={7}>
                        <div className="h-12 bg-muted/50 animate-pulse rounded" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : waitlist.length === 0 ? (
                  <TableRow className="border-border">
                    <TableCell colSpan={7} className="text-center py-12">
                      <div className="text-muted-foreground">
                        <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg">No one on the waitlist</p>
                        <p className="text-sm">Clients will appear here when slots are full</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  waitlist.map((entry) => (
                    <TableRow 
                      key={entry.id} 
                      className="border-border hover:bg-accent/30"
                      data-testid={`waitlist-row-${entry.id}`}
                    >
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
                        <div className="flex items-center gap-2">
                          <Scissors className="w-4 h-4 text-muted-foreground" />
                          {entry.service?.name || "Unknown"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          {format(new Date(entry.preferred_date), "MMM d, yyyy")}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          ± {entry.flexible_hours} hours
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono">{entry.contact_attempts}</span>
                        {entry.last_contacted && (
                          <p className="text-xs text-muted-foreground">
                            Last: {format(new Date(entry.last_contacted), "MMM d")}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {format(new Date(entry.created_at), "MMM d, yyyy")}
                      </TableCell>
                      <TableCell>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-muted-foreground hover:text-destructive"
                              data-testid={`remove-waitlist-${entry.id}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Remove from Waitlist?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will remove {entry.client?.name || "this client"} from the waitlist. 
                                They won't be notified when a slot opens up.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => removeFromWaitlist(entry.id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Remove
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center shrink-0">
                <Clock className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h4 className="font-medium mb-1">How Waitlist Filling Works</h4>
                <p className="text-sm text-muted-foreground">
                  When an appointment is cancelled, the system automatically contacts waitlist clients 
                  who match the cancelled time slot. Clients are contacted in order of when they joined 
                  the waitlist, with fewest contact attempts first.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
