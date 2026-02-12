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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
  Calendar as CalendarIcon,
  Clock,
  User,
  Scissors,
  Filter,
  Plus,
  ChevronLeft,
  ChevronRight,
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

const statusLabels = Object.fromEntries(
  statusOptions.filter((o) => o.value !== "all").map((o) => [o.value, o.label])
);

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

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState(null);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 20;

  // Allowed transitions map fetched from backend
  const [allowedTransitions, setAllowedTransitions] = useState({});

  // Shop timezone (e.g. "America/New_York") — fetched once on mount
  const [shopTimezone, setShopTimezone] = useState(null);

  // Create appointment dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [clients, setClients] = useState([]);
  // scheduled_at_local holds the datetime-local input value (no timezone)
  const [newApt, setNewApt] = useState({
    client_id: "",
    barber_id: "",
    service_id: "",
    scheduled_at: "",
    scheduled_at_local: "",
    notes: "",
  });

  useEffect(() => {
    fetchAppointments();
  }, [statusFilter, dateFilter, page]);

  useEffect(() => {
    fetchAllowedTransitions();
    fetchShopTimezone();
  }, []);

  const fetchAllowedTransitions = async () => {
    try {
      const response = await axios.get(`${API}/appointments/allowed-transitions`);
      setAllowedTransitions(response.data);
    } catch {
      // Fallback: show no action options (safe default)
    }
  };

  const fetchShopTimezone = async () => {
    try {
      const response = await axios.get(`${API}/shop`);
      setShopTimezone(response.data.timezone || "UTC");
    } catch {
      setShopTimezone("UTC");
    }
  };

  /**
   * Convert a datetime-local string (e.g. "2026-02-12T14:30") to a UTC ISO
   * string, interpreting the wall-clock time in the shop's IANA timezone
   * rather than the browser's local timezone.
   */
  const localInputToISO = (localValue) => {
    if (!localValue || !shopTimezone) return "";
    // Parse components directly — avoids any browser-timezone interpretation
    const [datePart, timePart] = localValue.split("T");
    const [year, month, day] = datePart.split("-").map(Number);
    const [hour, minute] = (timePart || "00:00").split(":").map(Number);

    // Create a Date treating these values as UTC (just a reference point)
    const naiveUTC = new Date(Date.UTC(year, month - 1, day, hour, minute));

    // Determine what wall-clock time the shop tz shows at this UTC instant
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: shopTimezone,
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hour12: false,
    }).formatToParts(naiveUTC);
    const g = (type) => parseInt(parts.find((p) => p.type === type)?.value || "0");
    const shopAtNaiveUTC = Date.UTC(g("year"), g("month") - 1, g("day"), g("hour"), g("minute"), g("second"));

    // offset = (shop display) − (UTC epoch)  → positive when shop is east of UTC
    const offsetMs = shopAtNaiveUTC - naiveUTC.getTime();

    // User entered shop-local time → UTC = naive − offset
    return new Date(naiveUTC.getTime() - offsetMs).toISOString();
  };

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
    } catch (error) {
      console.error("Failed to fetch appointments:", error);
      toast.error("Failed to load appointments");
    } finally {
      setLoading(false);
    }
  };

  const fetchFormData = async () => {
    try {
      const [b, s, c] = await Promise.all([
        axios.get(`${API}/barbers`),
        axios.get(`${API}/services`),
        axios.get(`${API}/clients?limit=200`),
      ]);
      setBarbers(b.data.barbers || []);
      setServices(s.data.services || []);
      setClients(c.data.clients || []);
    } catch {
      toast.error("Failed to load form data");
    }
  };

  const openCreateDialog = () => {
    fetchFormData();
    setNewApt({ client_id: "", barber_id: "", service_id: "", scheduled_at: "", scheduled_at_local: "", notes: "" });
    setCreateOpen(true);
  };

  const handleCreate = async () => {
    if (!newApt.client_id || !newApt.barber_id || !newApt.service_id || !newApt.scheduled_at) {
      toast.error("Client, barber, service, and date/time are required");
      return;
    }
    setCreating(true);
    try {
      const { scheduled_at_local, ...payload } = newApt;
      await axios.post(`${API}/appointments`, payload);
      toast.success("Appointment created");
      setCreateOpen(false);
      fetchAppointments();
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail || "Failed to create appointment");
    } finally {
      setCreating(false);
    }
  };

  const updateStatus = async (appointmentId, newStatus) => {
    try {
      await axios.patch(`${API}/appointments/${appointmentId}/status?status=${newStatus}`);
      toast.success("Status updated");
      fetchAppointments();
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail || "Failed to update status");
    }
  };

  const getValidTargets = (currentStatus) => {
    const targets = allowedTransitions[currentStatus] || [];
    return targets.map((v) => ({ value: v, label: statusLabels[v] || v }));
  };

  const formatDateTime = (dateString) => {
    const date = new Date(dateString);
    return {
      date: format(date, "MMM d, yyyy"),
      time: format(date, "h:mm a"),
    };
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <Layout title="Appointments">
      <div data-testid="appointments-page" className="space-y-6">
        {/* Filters */}
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center gap-4 justify-between">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <Filter className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Filters:</span>
                </div>

                <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); }}>
                  <SelectTrigger className="w-48 bg-input/50" data-testid="status-filter">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      data-testid="date-filter"
                      className={`w-48 justify-start text-left font-normal ${!dateFilter && "text-muted-foreground"}`}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {dateFilter ? format(dateFilter, "PPP") : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={dateFilter}
                      onSelect={(d) => { setDateFilter(d); setPage(0); }}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>

                {(statusFilter !== "all" || dateFilter) && (
                  <Button
                    variant="ghost"
                    onClick={() => { setStatusFilter("all"); setDateFilter(null); setPage(0); }}
                    className="text-muted-foreground"
                  >
                    Clear filters
                  </Button>
                )}
              </div>

              <Button onClick={openCreateDialog} data-testid="create-appointment-btn">
                <Plus className="w-4 h-4 mr-2" />
                New Appointment
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Create Appointment Dialog */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>New Appointment</DialogTitle>
              <DialogDescription>Book a new appointment for a client.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>Client *</Label>
                <Select value={newApt.client_id} onValueChange={(v) => setNewApt({ ...newApt, client_id: v })}>
                  <SelectTrigger data-testid="apt-client-select"><SelectValue placeholder="Select client" /></SelectTrigger>
                  <SelectContent>
                    {clients.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.name} ({c.phone})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Barber *</Label>
                <Select value={newApt.barber_id} onValueChange={(v) => setNewApt({ ...newApt, barber_id: v })}>
                  <SelectTrigger data-testid="apt-barber-select"><SelectValue placeholder="Select barber" /></SelectTrigger>
                  <SelectContent>
                    {barbers.map((b) => (
                      <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Service *</Label>
                <Select value={newApt.service_id} onValueChange={(v) => setNewApt({ ...newApt, service_id: v })}>
                  <SelectTrigger data-testid="apt-service-select"><SelectValue placeholder="Select service" /></SelectTrigger>
                  <SelectContent>
                    {services.map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name} — ${s.price}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Date & Time *{shopTimezone ? ` (${shopTimezone.replace(/_/g, " ")})` : ""}</Label>
                <Input
                  type="datetime-local"
                  value={newApt.scheduled_at_local}
                  onChange={(e) => {
                    const local = e.target.value;
                    setNewApt({
                      ...newApt,
                      scheduled_at_local: local,
                      scheduled_at: local ? localInputToISO(local) : "",
                    });
                  }}
                  data-testid="apt-datetime-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Notes</Label>
                <Input
                  placeholder="Optional notes"
                  value={newApt.notes}
                  onChange={(e) => setNewApt({ ...newApt, notes: e.target.value })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={creating} data-testid="submit-appointment-btn">
                {creating ? "Booking..." : "Book"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Appointments Table */}
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
                      <TableCell colSpan={7}>
                        <div className="h-12 bg-muted/50 animate-pulse rounded" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : appointments.length === 0 ? (
                  <TableRow className="border-border">
                    <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                      No appointments found
                    </TableCell>
                  </TableRow>
                ) : (
                  appointments.map((apt) => {
                    const { date, time } = formatDateTime(apt.scheduled_at);
                    const validTargets = getValidTargets(apt.status);
                    return (
                      <TableRow
                        key={apt.id}
                        className="border-border hover:bg-accent/30"
                        data-testid={`appointment-row-${apt.id}`}
                      >
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
                              <Clock className="w-3 h-3" />
                              {time}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={`${statusColors[apt.status] || "bg-secondary"}`}>
                            {apt.status.replace(/_/g, " ")}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {apt.deposit_required ? (
                            <Badge className={apt.deposit_paid ? "bg-emerald-500/20 text-emerald-400" : "bg-orange-500/20 text-orange-400"}>
                              ${apt.deposit_amount} {apt.deposit_paid ? "Paid" : "Pending"}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {validTargets.length > 0 ? (
                            <Select
                              value=""
                              onValueChange={(value) => updateStatus(apt.id, value)}
                            >
                              <SelectTrigger className="w-36 h-8 text-xs" data-testid={`status-action-${apt.id}`}>
                                <SelectValue placeholder="Change status" />
                              </SelectTrigger>
                              <SelectContent>
                                {validTargets.map((option) => (
                                  <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <span className="text-xs text-muted-foreground">No actions</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
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
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
