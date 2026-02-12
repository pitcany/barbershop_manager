import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Calendar } from "../components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "../components/ui/popover";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
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
import { toast } from "sonner";
import { 
  Search, 
  Calendar as CalendarIcon, 
  Clock,
  User,
  Scissors,
  Filter,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Plus
} from "lucide-react";
import { format } from "date-fns";

const statusOptions = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "confirmed", label: "Confirmed" },
  { value: "deposit_pending", label: "Deposit Pending" },
  { value: "deposit_paid", label: "Deposit Paid" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
  { value: "no_show", label: "No Show" },
  { value: "rescheduled", label: "Rescheduled" },
];

const statusColors = {
  pending: "bg-yellow-500/20 text-yellow-400",
  confirmed: "bg-emerald-500/20 text-emerald-400",
  deposit_pending: "bg-orange-500/20 text-orange-400",
  deposit_paid: "bg-emerald-500/20 text-emerald-400",
  completed: "bg-blue-500/20 text-blue-400",
  cancelled: "bg-red-500/20 text-red-400",
  no_show: "bg-red-500/20 text-red-400",
  rescheduled: "bg-purple-500/20 text-purple-400",
};

const timeSlots = [];
for (let h = 8; h <= 19; h++) {
  for (let m = 0; m < 60; m += 30) {
    const hh = String(h).padStart(2, "0");
    const mm = String(m).padStart(2, "0");
    const label = `${h > 12 ? h - 12 : h}:${mm} ${h >= 12 ? "PM" : "AM"}`;
    timeSlots.push({ value: `${hh}:${mm}`, label });
  }
}

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState(null);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 20;

  // New appointment modal state
  const [newModalOpen, setNewModalOpen] = useState(false);
  const [clients, setClients] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [clientSearch, setClientSearch] = useState("");
  const [newApt, setNewApt] = useState({
    client_id: "", barber_id: "", service_id: "", date: null, time: "", notes: ""
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { fetchAppointments(); }, [statusFilter, dateFilter, page]);

  const fetchAppointments = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.append("status", statusFilter);
      if (dateFilter) params.append("date", format(dateFilter, "yyyy-MM-dd"));
      params.append("limit", limit);
      params.append("skip", page * limit);
      const response = await axios.get(`${API}/appointments?${params}`);
      setAppointments(response.data.appointments);
      setTotal(response.data.total);
    } catch { toast.error("Failed to load appointments"); }
    finally { setLoading(false); }
  };

  const updateStatus = async (appointmentId, newStatus) => {
    try {
      await axios.patch(`${API}/appointments/${appointmentId}/status?status=${newStatus}`);
      toast.success("Status updated");
      fetchAppointments();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to update status"); }
  };

  const initiateDeposit = async (appointmentId) => {
    try {
      const res = await axios.post(`${API}/payments/create-deposit/${appointmentId}`, null, {
        headers: { "x-origin": window.location.origin }
      });
      if (res.data.checkout_url) {
        navigator.clipboard.writeText(res.data.checkout_url).then(() => {
          toast.success("Deposit link copied to clipboard");
        }).catch(() => { console.log("Deposit link:", res.data.checkout_url); });
      }
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to create deposit link"); }
  };

  // Open modal and load data for dropdowns
  const openNewModal = async () => {
    setNewApt({ client_id: "", barber_id: "", service_id: "", date: null, time: "", notes: "" });
    setClientSearch("");
    setNewModalOpen(true);
    try {
      const [b, s, c] = await Promise.all([
        axios.get(`${API}/barbers`),
        axios.get(`${API}/services`),
        axios.get(`${API}/clients?limit=200`),
      ]);
      setBarbers(b.data.barbers);
      setServices(s.data.services);
      setClients(c.data.clients);
    } catch { toast.error("Failed to load data for booking"); }
  };

  const handleCreateAppointment = async () => {
    if (!newApt.client_id || !newApt.barber_id || !newApt.service_id || !newApt.date || !newApt.time) {
      toast.error("Please fill all required fields");
      return;
    }
    setSubmitting(true);
    try {
      const dateStr = format(newApt.date, "yyyy-MM-dd");
      const scheduled_at = `${dateStr}T${newApt.time}:00`;
      await axios.post(`${API}/appointments`, {
        client_id: newApt.client_id,
        barber_id: newApt.barber_id,
        service_id: newApt.service_id,
        scheduled_at,
        notes: newApt.notes,
      });
      toast.success("Appointment created");
      setNewModalOpen(false);
      fetchAppointments();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to create appointment"); }
    finally { setSubmitting(false); }
  };

  const formatDateTime = (dateString) => {
    const date = new Date(dateString);
    return { date: format(date, "MMM d, yyyy"), time: format(date, "h:mm a") };
  };

  const filteredClients = clients.filter(c =>
    !clientSearch || c.name.toLowerCase().includes(clientSearch.toLowerCase()) || c.phone.includes(clientSearch)
  );

  const totalPages = Math.ceil(total / limit);

  return (
    <Layout title="Appointments">
      <div data-testid="appointments-page" className="space-y-6">
        {/* Header with New Appointment */}
        <div className="flex items-center justify-between">
          <div />
          <Button onClick={openNewModal} data-testid="new-appointment-btn" className="gap-2">
            <Plus className="w-4 h-4" /> New Appointment
          </Button>
        </div>

        {/* Filters */}
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Filters:</span>
              </div>
              
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-48 bg-input/50" data-testid="status-filter">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" data-testid="date-filter" className={`w-48 justify-start text-left font-normal ${!dateFilter && "text-muted-foreground"}`}>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {dateFilter ? format(dateFilter, "PPP") : "Pick a date"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar mode="single" selected={dateFilter} onSelect={setDateFilter} initialFocus />
                </PopoverContent>
              </Popover>

              {(statusFilter !== "all" || dateFilter) && (
                <Button variant="ghost" onClick={() => { setStatusFilter("all"); setDateFilter(null); }} className="text-muted-foreground">
                  Clear filters
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Table */}
        <Card className="bg-card border-border">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">Client</TableHead>
                  <TableHead className="text-muted-foreground">Service</TableHead>
                  <TableHead className="text-muted-foreground">Barber</TableHead>
                  <TableHead className="text-muted-foreground">Date & Time</TableHead>
                  <TableHead className="text-muted-foreground">Status</TableHead>
                  <TableHead className="text-muted-foreground">Deposit</TableHead>
                  <TableHead className="text-muted-foreground">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <TableRow key={i} className="border-border">
                      <TableCell colSpan={7}><div className="h-12 bg-muted/50 animate-pulse rounded" /></TableCell>
                    </TableRow>
                  ))
                ) : appointments.length === 0 ? (
                  <TableRow className="border-border">
                    <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">No appointments found</TableCell>
                  </TableRow>
                ) : appointments.map((apt) => {
                  const { date, time } = formatDateTime(apt.scheduled_at);
                  return (
                    <TableRow key={apt.id} className="border-border hover:bg-accent/30" data-testid={`appointment-row-${apt.id}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <User className="w-4 h-4 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{apt.client?.name || "Unknown"}</p>
                            <p className="text-xs text-muted-foreground">{apt.client?.phone}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Scissors className="w-4 h-4 text-muted-foreground" />
                          {apt.service?.name || "Unknown"}
                        </div>
                      </TableCell>
                      <TableCell>{apt.barber?.name || "Unknown"}</TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{date}</p>
                          <p className="text-sm text-muted-foreground flex items-center gap-1">
                            <Clock className="w-3 h-3" />{time}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={`${statusColors[apt.status] || "bg-secondary"}`}>{apt.status.replace(/_/g, " ")}</Badge>
                      </TableCell>
                      <TableCell>
                        {apt.deposit_required ? (
                          <Badge className={apt.deposit_paid ? "bg-emerald-500/20 text-emerald-400" : "bg-orange-500/20 text-orange-400"}>
                            ${apt.deposit_amount} {apt.deposit_paid ? "Paid" : "Pending"}
                          </Badge>
                        ) : <span className="text-muted-foreground">-</span>}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {(apt.status === "deposit_pending" || (apt.status === "pending" && apt.deposit_required && !apt.deposit_paid)) && (
                            <Button variant="outline" size="sm"
                              className="h-8 text-xs gap-1 border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
                              onClick={() => initiateDeposit(apt.id)} data-testid={`send-deposit-link-btn-${apt.id}`}>
                              <CreditCard className="w-3 h-3" /> Send Deposit Link
                            </Button>
                          )}
                          <Select value={apt.status} onValueChange={(value) => updateStatus(apt.id, value)}>
                            <SelectTrigger className="w-32 h-8 text-xs"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {statusOptions.slice(1).map((option) => (
                                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {page * limit + 1} to {Math.min((page + 1) * limit, total)} of {total} appointments
            </p>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm">Page {page + 1} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* ===== NEW APPOINTMENT DIALOG ===== */}
        <Dialog open={newModalOpen} onOpenChange={setNewModalOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>New Appointment</DialogTitle>
              <DialogDescription>Book a walk-in or phone appointment for a client.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto">
              {/* Client */}
              <div>
                <Label>Client *</Label>
                <Input placeholder="Search clients..." value={clientSearch} onChange={(e) => setClientSearch(e.target.value)} data-testid="client-search-input" className="mb-2" />
                <Select value={newApt.client_id} onValueChange={(v) => setNewApt({ ...newApt, client_id: v })}>
                  <SelectTrigger data-testid="client-select"><SelectValue placeholder="Select client" /></SelectTrigger>
                  <SelectContent>
                    {filteredClients.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name} — {c.phone}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Barber */}
              <div>
                <Label>Barber *</Label>
                <Select value={newApt.barber_id} onValueChange={(v) => setNewApt({ ...newApt, barber_id: v })}>
                  <SelectTrigger data-testid="barber-select"><SelectValue placeholder="Select barber" /></SelectTrigger>
                  <SelectContent>
                    {barbers.map((b) => (<SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>

              {/* Service */}
              <div>
                <Label>Service *</Label>
                <Select value={newApt.service_id} onValueChange={(v) => setNewApt({ ...newApt, service_id: v })}>
                  <SelectTrigger data-testid="service-select"><SelectValue placeholder="Select service" /></SelectTrigger>
                  <SelectContent>
                    {services.map((s) => (<SelectItem key={s.id} value={s.id}>{s.name} — ${s.price}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>

              {/* Date */}
              <div>
                <Label>Date *</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" data-testid="apt-date-picker" className={`w-full justify-start text-left font-normal ${!newApt.date && "text-muted-foreground"}`}>
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {newApt.date ? format(newApt.date, "PPP") : "Select date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar mode="single" selected={newApt.date} onSelect={(d) => setNewApt({ ...newApt, date: d })} initialFocus />
                  </PopoverContent>
                </Popover>
              </div>

              {/* Time */}
              <div>
                <Label>Time *</Label>
                <Select value={newApt.time} onValueChange={(v) => setNewApt({ ...newApt, time: v })}>
                  <SelectTrigger data-testid="apt-time-select"><SelectValue placeholder="Select time" /></SelectTrigger>
                  <SelectContent>
                    {timeSlots.map((t) => (<SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>

              {/* Notes */}
              <div>
                <Label>Notes</Label>
                <Textarea data-testid="apt-notes-input" value={newApt.notes} onChange={(e) => setNewApt({ ...newApt, notes: e.target.value })} placeholder="Optional notes..." rows={2} />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setNewModalOpen(false)}>Cancel</Button>
              <Button onClick={handleCreateAppointment} disabled={submitting} data-testid="create-appointment-btn">
                {submitting ? "Creating..." : "Create Appointment"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
}
