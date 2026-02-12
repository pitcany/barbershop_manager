import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Label } from "../components/ui/label";
import { Checkbox } from "../components/ui/checkbox";
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
  User,
  Phone,
  Mail,
  Plus,
  Calendar,
  MessageSquare,
  AlertTriangle,
  DollarSign,
  ChevronRight,
  UserPlus
} from "lucide-react";
import { format } from "date-fns";

export default function ClientsPage() {
  const navigate = useNavigate();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newClient, setNewClient] = useState({
    name: "",
    phone: "",
    email: "",
    sms_consent: true
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchClients();
  }, [searchTerm]);

  const fetchClients = async () => {
    try {
      const params = new URLSearchParams();
      if (searchTerm) params.append("search", searchTerm);
      params.append("limit", "100");

      const response = await axios.get(`${API}/clients?${params}`);
      setClients(response.data.clients);
    } catch (error) {
      console.error("Failed to fetch clients:", error);
      toast.error("Failed to load clients");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateClient = async () => {
    if (!newClient.name || !newClient.phone) {
      toast.error("Name and phone are required");
      return;
    }

    setCreating(true);
    try {
      await axios.post(`${API}/clients`, newClient);
      toast.success("Client created successfully");
      setShowCreateDialog(false);
      setNewClient({ name: "", phone: "", email: "", sms_consent: true });
      fetchClients();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create client");
    } finally {
      setCreating(false);
    }
  };

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, "");
    if (digits.length === 10) return `+1${digits}`;
    if (digits.length === 11 && digits.startsWith("1")) return `+${digits}`;
    if (value.startsWith("+")) return value;
    return `+${digits}`;
  };

  return (
    <Layout title="Clients">
      <div data-testid="clients-page" className="space-y-6">
        {/* Header with Search and Create */}
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  data-testid="client-search"
                  placeholder="Search by name or phone..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 bg-input/50 border-input"
                />
              </div>

              <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
                <DialogTrigger asChild>
                  <Button data-testid="create-client-button" className="bg-primary text-primary-foreground">
                    <UserPlus className="w-4 h-4 mr-2" />
                    Add Client
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle className="font-heading">Add New Client</DialogTitle>
                    <DialogDescription>
                      Create a new client profile. SMS consent allows you to send appointment reminders.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">Name *</Label>
                      <Input
                        id="name"
                        data-testid="new-client-name"
                        placeholder="John Smith"
                        value={newClient.name}
                        onChange={(e) => setNewClient(prev => ({ ...prev, name: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="phone">Phone *</Label>
                      <Input
                        id="phone"
                        data-testid="new-client-phone"
                        placeholder="+1 (555) 123-4567"
                        value={newClient.phone}
                        onChange={(e) => setNewClient(prev => ({ ...prev, phone: e.target.value }))}
                        onBlur={(e) => {
                          if (e.target.value) {
                            setNewClient(prev => ({ ...prev, phone: formatPhone(e.target.value) }));
                          }
                        }}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">Email (optional)</Label>
                      <Input
                        id="email"
                        data-testid="new-client-email"
                        type="email"
                        placeholder="john@example.com"
                        value={newClient.email}
                        onChange={(e) => setNewClient(prev => ({ ...prev, email: e.target.value }))}
                      />
                    </div>
                    <div className="flex items-center space-x-3">
                      <Checkbox
                        id="sms_consent"
                        data-testid="new-client-sms-consent"
                        checked={newClient.sms_consent}
                        onCheckedChange={(checked) => setNewClient(prev => ({ ...prev, sms_consent: checked }))}
                      />
                      <Label htmlFor="sms_consent" className="font-normal">
                        Client agrees to receive SMS notifications
                      </Label>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                      Cancel
                    </Button>
                    <Button
                      onClick={handleCreateClient}
                      disabled={creating}
                      data-testid="submit-create-client"
                      className="bg-primary text-primary-foreground"
                    >
                      {creating ? "Creating..." : "Create Client"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </CardContent>
        </Card>

        {/* Clients Table */}
        <Card className="bg-card border-border">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">Client</TableHead>
                  <TableHead className="text-muted-foreground">Contact</TableHead>
                  <TableHead className="text-muted-foreground">SMS Consent</TableHead>
                  <TableHead className="text-muted-foreground">No-Shows</TableHead>
                  <TableHead className="text-muted-foreground">Joined</TableHead>
                  <TableHead className="text-muted-foreground"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <TableRow key={i} className="border-border">
                      <TableCell colSpan={6}>
                        <div className="h-12 bg-muted/50 animate-pulse rounded" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : clients.length === 0 ? (
                  <TableRow className="border-border">
                    <TableCell colSpan={6} className="text-center py-12">
                      <div className="text-muted-foreground">
                        <User className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg">No clients found</p>
                        <p className="text-sm">{searchTerm ? "Try a different search" : "Add your first client to get started"}</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  clients.map((client) => (
                    <TableRow
                      key={client.id}
                      className="border-border hover:bg-accent/30 cursor-pointer"
                      onClick={() => navigate(`/clients/${client.id}`)}
                      data-testid={`client-row-${client.id}`}
                    >
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-secondary rounded-full flex items-center justify-center">
                            <User className="w-5 h-5 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="font-medium">{client.name}</p>
                            <p className="text-xs text-muted-foreground">ID: {client.id.slice(0, 8)}...</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <p className="text-sm flex items-center gap-1">
                            <Phone className="w-3 h-3 text-muted-foreground" />
                            {client.phone}
                          </p>
                          {client.email && (
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Mail className="w-3 h-3" />
                              {client.email}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge className={client.sms_consent ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}>
                          {client.sms_consent ? "Granted" : "Not Granted"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {client.no_shows > 0 ? (
                          <Badge className="bg-red-500/20 text-red-400">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            {client.no_shows}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {client.created_at ? format(new Date(client.created_at), "MMM d, yyyy") : "-"}
                      </TableCell>
                      <TableCell>
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Summary */}
        <div className="text-sm text-muted-foreground text-center">
          {clients.length} client{clients.length !== 1 ? "s" : ""} found
        </div>
      </div>
    </Layout>
  );
}
