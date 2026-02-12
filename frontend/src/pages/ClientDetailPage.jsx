import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import { toast } from "sonner";
import { 
  User,
  Phone,
  Mail,
  Calendar,
  MessageSquare,
  AlertTriangle,
  DollarSign,
  ArrowLeft,
  Clock,
  Scissors,
  Plus,
  Users,
  CheckCircle,
  XCircle
} from "lucide-react";
import { format } from "date-fns";

const statusColors = {
  pending: "bg-yellow-500/20 text-yellow-400",
  confirmed: "bg-emerald-500/20 text-emerald-400",
  deposit_pending: "bg-orange-500/20 text-orange-400",
  deposit_paid: "bg-emerald-500/20 text-emerald-400",
  completed: "bg-blue-500/20 text-blue-400",
  cancelled: "bg-red-500/20 text-red-400",
  no_show: "bg-red-500/20 text-red-400",
};

export default function ClientDetailPage() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const [clientData, setClientData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [availableSlots, setAvailableSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  
  // Book appointment state
  const [showBookDialog, setShowBookDialog] = useState(false);
  const [bookingData, setBookingData] = useState({
    barber_id: "",
    service_id: "",
    date: "",
    slot: null
  });
  const [booking, setBooking] = useState(false);
  
  // Add to waitlist state
  const [showWaitlistDialog, setShowWaitlistDialog] = useState(false);
  const [waitlistData, setWaitlistData] = useState({
    service_id: "",
    preferred_date: "",
    barber_id: "",
    flexible_hours: 2
  });
  const [addingToWaitlist, setAddingToWaitlist] = useState(false);

  useEffect(() => {
    fetchClientData();
    fetchBarbers();
    fetchServices();
  }, [clientId]);

  useEffect(() => {
    if (bookingData.date && bookingData.service_id) {
      fetchAvailableSlots();
    }
  }, [bookingData.date, bookingData.service_id, bookingData.barber_id]);

  const fetchClientData = async () => {
    try {
      const response = await axios.get(`${API}/clients/${clientId}/history`);
      setClientData(response.data);
    } catch (error) {
      console.error("Failed to fetch client:", error);
      toast.error("Failed to load client data");
      navigate("/clients");
    } finally {
      setLoading(false);
    }
  };

  const fetchBarbers = async () => {
    try {
      const response = await axios.get(`${API}/barbers`);
      setBarbers(response.data.barbers);
    } catch (error) {
      console.error("Failed to fetch barbers:", error);
    }
  };

  const fetchServices = async () => {
    try {
      const response = await axios.get(`${API}/services`);
      setServices(response.data.services);
    } catch (error) {
      console.error("Failed to fetch services:", error);
    }
  };

  const fetchAvailableSlots = async () => {
    setLoadingSlots(true);
    try {
      const params = new URLSearchParams();
      params.append("date", bookingData.date);
      if (bookingData.service_id) params.append("service_id", bookingData.service_id);
      if (bookingData.barber_id) params.append("barber_id", bookingData.barber_id);
      
      const response = await axios.get(`${API}/scheduling/availability?${params}`);
      setAvailableSlots(response.data.slots);
    } catch (error) {
      console.error("Failed to fetch slots:", error);
      setAvailableSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  };

  const handleBookAppointment = async () => {
    if (!bookingData.slot) {
      toast.error("Please select a time slot");
      return;
    }

    setBooking(true);
    try {
      await axios.post(`${API}/appointments`, {
        client_id: clientId,
        barber_id: bookingData.slot.barber_id,
        service_id: bookingData.service_id,
        scheduled_at: bookingData.slot.start
      });
      toast.success("Appointment booked successfully");
      setShowBookDialog(false);
      setBookingData({ barber_id: "", service_id: "", date: "", slot: null });
      fetchClientData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to book appointment");
    } finally {
      setBooking(false);
    }
  };

  const handleAddToWaitlist = async () => {
    if (!waitlistData.service_id || !waitlistData.preferred_date) {
      toast.error("Service and preferred date are required");
      return;
    }

    setAddingToWaitlist(true);
    try {
      const params = new URLSearchParams();
      params.append("service_id", waitlistData.service_id);
      params.append("preferred_date", waitlistData.preferred_date);
      if (waitlistData.barber_id) params.append("barber_id", waitlistData.barber_id);
      params.append("flexible_hours", waitlistData.flexible_hours);

      await axios.post(`${API}/clients/${clientId}/waitlist?${params}`);
      toast.success("Added to waitlist");
      setShowWaitlistDialog(false);
      setWaitlistData({ service_id: "", preferred_date: "", barber_id: "", flexible_hours: 2 });
      fetchClientData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add to waitlist");
    } finally {
      setAddingToWaitlist(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-muted rounded w-48" />
          <div className="h-64 bg-muted rounded" />
        </div>
      </Layout>
    );
  }

  if (!clientData) return null;

  const { client, appointments, messages, stats, waitlist_entry } = clientData;

  return (
    <Layout>
      <div data-testid="client-detail-page" className="space-y-6">
        {/* Back button and header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/clients")}
            data-testid="back-to-clients"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex-1">
            <h1 className="font-heading text-3xl font-bold">{client.name}</h1>
            <p className="text-muted-foreground flex items-center gap-2">
              <Phone className="w-4 h-4" /> {client.phone}
              {client.email && (
                <>
                  <span className="mx-2">•</span>
                  <Mail className="w-4 h-4" /> {client.email}
                </>
              )}
            </p>
          </div>
          
          {/* Action buttons */}
          <div className="flex gap-2">
            <Dialog open={showBookDialog} onOpenChange={setShowBookDialog}>
              <DialogTrigger asChild>
                <Button data-testid="book-appointment-button" className="bg-primary text-primary-foreground">
                  <Calendar className="w-4 h-4 mr-2" />
                  Book Appointment
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle className="font-heading">Book Appointment</DialogTitle>
                  <DialogDescription>
                    Select a service, date, and available time slot.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>Service *</Label>
                    <Select
                      value={bookingData.service_id}
                      onValueChange={(val) => setBookingData(prev => ({ ...prev, service_id: val, slot: null }))}
                    >
                      <SelectTrigger data-testid="booking-service-select">
                        <SelectValue placeholder="Select service" />
                      </SelectTrigger>
                      <SelectContent>
                        {services.map((s) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.name} - ${s.price} ({s.duration_minutes}min)
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Preferred Barber (optional)</Label>
                    <Select
                      value={bookingData.barber_id || "any"}
                      onValueChange={(val) => setBookingData(prev => ({ ...prev, barber_id: val === "any" ? "" : val, slot: null }))}
                    >
                      <SelectTrigger data-testid="booking-barber-select">
                        <SelectValue placeholder="Any available" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="any">Any available</SelectItem>
                        {barbers.map((b) => (
                          <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Date *</Label>
                    <Input
                      type="date"
                      data-testid="booking-date-input"
                      min={new Date().toISOString().split('T')[0]}
                      value={bookingData.date}
                      onChange={(e) => setBookingData(prev => ({ ...prev, date: e.target.value, slot: null }))}
                    />
                  </div>
                  
                  {bookingData.date && bookingData.service_id && (
                    <div className="space-y-2">
                      <Label>Available Slots</Label>
                      {loadingSlots ? (
                        <div className="text-sm text-muted-foreground">Loading slots...</div>
                      ) : availableSlots.length === 0 ? (
                        <div className="text-sm text-muted-foreground">No slots available for this date</div>
                      ) : (
                        <ScrollArea className="h-48 border rounded-md p-2">
                          <div className="grid grid-cols-2 gap-2">
                            {availableSlots.map((slot, idx) => (
                              <Button
                                key={idx}
                                variant={bookingData.slot?.start === slot.start ? "default" : "outline"}
                                size="sm"
                                className="justify-start"
                                onClick={() => setBookingData(prev => ({ ...prev, slot }))}
                                data-testid={`slot-${idx}`}
                              >
                                <Clock className="w-3 h-3 mr-2" />
                                {format(new Date(slot.start), "h:mm a")}
                                <span className="text-xs ml-auto opacity-70">{slot.barber_name}</span>
                              </Button>
                            ))}
                          </div>
                        </ScrollArea>
                      )}
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowBookDialog(false)}>Cancel</Button>
                  <Button
                    onClick={handleBookAppointment}
                    disabled={booking || !bookingData.slot}
                    data-testid="confirm-booking-button"
                    className="bg-primary text-primary-foreground"
                  >
                    {booking ? "Booking..." : "Book Appointment"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {!waitlist_entry && (
              <Dialog open={showWaitlistDialog} onOpenChange={setShowWaitlistDialog}>
                <DialogTrigger asChild>
                  <Button variant="outline" data-testid="add-to-waitlist-button">
                    <Users className="w-4 h-4 mr-2" />
                    Add to Waitlist
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle className="font-heading">Add to Waitlist</DialogTitle>
                    <DialogDescription>
                      Client will be notified when a matching slot becomes available.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>Service *</Label>
                      <Select
                        value={waitlistData.service_id}
                        onValueChange={(val) => setWaitlistData(prev => ({ ...prev, service_id: val }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select service" />
                        </SelectTrigger>
                        <SelectContent>
                          {services.map((s) => (
                            <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Preferred Date *</Label>
                      <Input
                        type="datetime-local"
                        min={new Date().toISOString().slice(0, 16)}
                        value={waitlistData.preferred_date}
                        onChange={(e) => setWaitlistData(prev => ({ ...prev, preferred_date: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Flexibility (hours)</Label>
                      <Input
                        type="number"
                        min="1"
                        max="8"
                        value={waitlistData.flexible_hours}
                        onChange={(e) => setWaitlistData(prev => ({ ...prev, flexible_hours: parseInt(e.target.value) }))}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowWaitlistDialog(false)}>Cancel</Button>
                    <Button
                      onClick={handleAddToWaitlist}
                      disabled={addingToWaitlist}
                      className="bg-primary text-primary-foreground"
                    >
                      {addingToWaitlist ? "Adding..." : "Add to Waitlist"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <Calendar className="w-5 h-5 text-primary" />
                <div>
                  <p className="text-xs text-muted-foreground">Total Visits</p>
                  <p className="font-mono font-medium text-lg">{stats.total_appointments}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="text-xs text-muted-foreground">Completed</p>
                  <p className="font-mono font-medium text-lg">{stats.completed_appointments}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                <div>
                  <p className="text-xs text-muted-foreground">No-Shows</p>
                  <p className="font-mono font-medium text-lg">{stats.no_shows}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <XCircle className="w-5 h-5 text-yellow-400" />
                <div>
                  <p className="text-xs text-muted-foreground">No-Show Rate</p>
                  <p className="font-mono font-medium text-lg">{stats.no_show_rate}%</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <DollarSign className="w-5 h-5 text-primary" />
                <div>
                  <p className="text-xs text-muted-foreground">Total Spent</p>
                  <p className="font-mono font-medium text-lg">${stats.total_spent}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Waitlist badge */}
        {waitlist_entry && (
          <Card className="bg-orange-500/10 border-orange-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <Users className="w-5 h-5 text-orange-400" />
              <div>
                <p className="font-medium text-orange-400">On Waitlist</p>
                <p className="text-sm text-muted-foreground">
                  Waiting for slot around {format(new Date(waitlist_entry.preferred_date), "MMM d, yyyy h:mm a")}
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tabs for Appointments and Messages */}
        <Tabs defaultValue="appointments" className="space-y-4">
          <TabsList className="bg-secondary">
            <TabsTrigger value="appointments" data-testid="appointments-tab">
              <Calendar className="w-4 h-4 mr-2" />
              Appointments ({appointments.length})
            </TabsTrigger>
            <TabsTrigger value="messages" data-testid="messages-tab">
              <MessageSquare className="w-4 h-4 mr-2" />
              Messages ({messages.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="appointments">
            <Card className="bg-card border-border">
              <CardContent className="p-0">
                {appointments.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    <Calendar className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No appointments yet</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {appointments.map((apt) => (
                      <div key={apt.id} className="p-4 hover:bg-accent/30">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 bg-secondary rounded-lg flex items-center justify-center">
                              <Scissors className="w-5 h-5 text-muted-foreground" />
                            </div>
                            <div>
                              <p className="font-medium">{apt.service?.name || "Service"}</p>
                              <p className="text-sm text-muted-foreground">
                                {apt.barber?.name || "Barber"} • {format(new Date(apt.scheduled_at), "MMM d, yyyy 'at' h:mm a")}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge className={statusColors[apt.status] || "bg-secondary"}>
                              {apt.status.replace(/_/g, " ")}
                            </Badge>
                            {apt.price > 0 && (
                              <p className="text-sm text-muted-foreground mt-1">${apt.price}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="messages">
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                {messages.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No messages yet</p>
                  </div>
                ) : (
                  <ScrollArea className="h-96">
                    <div className="space-y-3">
                      {messages.slice().reverse().map((msg, idx) => (
                        <div
                          key={msg.id || idx}
                          className={`flex ${msg.direction === "outbound" ? "justify-end" : "justify-start"}`}
                        >
                          <div
                            className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                              msg.direction === "outbound"
                                ? "bg-primary text-primary-foreground rounded-br-sm"
                                : "bg-secondary text-foreground rounded-bl-sm"
                            }`}
                          >
                            <p className="text-sm">{msg.content}</p>
                            <p className={`text-xs mt-1 ${msg.direction === "outbound" ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                              {format(new Date(msg.created_at), "MMM d, h:mm a")}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}
