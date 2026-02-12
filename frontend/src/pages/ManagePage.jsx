import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Users, Scissors } from "lucide-react";

export default function ManagePage() {
  const [barbers, setBarbers] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  // Barber dialog
  const [barberDialogOpen, setBarberDialogOpen] = useState(false);
  const [editingBarber, setEditingBarber] = useState(null);
  const [barberForm, setBarberForm] = useState({ name: "", email: "", phone: "" });

  // Service dialog
  const [serviceDialogOpen, setServiceDialogOpen] = useState(false);
  const [editingService, setEditingService] = useState(null);
  const [serviceForm, setServiceForm] = useState({ name: "", description: "", duration_minutes: 30, price: 0 });

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [b, s] = await Promise.all([
        axios.get(`${API}/barbers`),
        axios.get(`${API}/services`),
      ]);
      setBarbers(b.data.barbers);
      setServices(s.data.services);
    } catch { toast.error("Failed to load data"); }
    finally { setLoading(false); }
  };

  // ===== BARBER CRUD =====
  const openBarberDialog = (barber = null) => {
    setEditingBarber(barber);
    setBarberForm(barber ? { name: barber.name, email: barber.email || "", phone: barber.phone || "" } : { name: "", email: "", phone: "" });
    setBarberDialogOpen(true);
  };

  const saveBarber = async () => {
    if (!barberForm.name.trim()) { toast.error("Name is required"); return; }
    try {
      if (editingBarber) {
        await axios.patch(`${API}/barbers/${editingBarber.id}`, barberForm);
        toast.success("Barber updated");
      } else {
        await axios.post(`${API}/barbers`, barberForm);
        toast.success("Barber added");
      }
      setBarberDialogOpen(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to save barber"); }
  };

  const deleteBarber = async (id) => {
    try {
      await axios.delete(`${API}/barbers/${id}`);
      toast.success("Barber removed");
      fetchAll();
    } catch { toast.error("Failed to remove barber"); }
  };

  // ===== SERVICE CRUD =====
  const openServiceDialog = (service = null) => {
    setEditingService(service);
    setServiceForm(service
      ? { name: service.name, description: service.description || "", duration_minutes: service.duration_minutes, price: service.price }
      : { name: "", description: "", duration_minutes: 30, price: 0 });
    setServiceDialogOpen(true);
  };

  const saveService = async () => {
    if (!serviceForm.name.trim()) { toast.error("Name is required"); return; }
    if (serviceForm.price < 0) { toast.error("Price must be >= 0"); return; }
    try {
      const payload = { ...serviceForm, price: parseFloat(serviceForm.price), duration_minutes: parseInt(serviceForm.duration_minutes) };
      if (editingService) {
        await axios.patch(`${API}/services/${editingService.id}`, payload);
        toast.success("Service updated");
      } else {
        await axios.post(`${API}/services`, payload);
        toast.success("Service added");
      }
      setServiceDialogOpen(false);
      fetchAll();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to save service"); }
  };

  const deleteService = async (id) => {
    try {
      await axios.delete(`${API}/services/${id}`);
      toast.success("Service removed");
      fetchAll();
    } catch { toast.error("Failed to remove service"); }
  };

  return (
    <Layout title="Manage Shop">
      <div data-testid="manage-page" className="space-y-6">
        <Tabs defaultValue="barbers" className="w-full">
          <TabsList className="bg-card border border-border">
            <TabsTrigger value="barbers" data-testid="tab-barbers" className="gap-2">
              <Users className="w-4 h-4" /> Barbers
            </TabsTrigger>
            <TabsTrigger value="services" data-testid="tab-services" className="gap-2">
              <Scissors className="w-4 h-4" /> Services
            </TabsTrigger>
          </TabsList>

          {/* ===== BARBERS TAB ===== */}
          <TabsContent value="barbers" className="mt-6">
            <Card className="bg-card border-border">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Barbers</CardTitle>
                <Button onClick={() => openBarberDialog()} data-testid="add-barber-btn" size="sm" className="gap-2">
                  <Plus className="w-4 h-4" /> Add Barber
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="border-border hover:bg-transparent">
                      <TableHead className="text-muted-foreground">Name</TableHead>
                      <TableHead className="text-muted-foreground">Email</TableHead>
                      <TableHead className="text-muted-foreground">Phone</TableHead>
                      <TableHead className="text-muted-foreground text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      [...Array(3)].map((_, i) => (
                        <TableRow key={i} className="border-border">
                          <TableCell colSpan={4}><div className="h-10 bg-muted/50 animate-pulse rounded" /></TableCell>
                        </TableRow>
                      ))
                    ) : barbers.length === 0 ? (
                      <TableRow className="border-border">
                        <TableCell colSpan={4} className="text-center py-12 text-muted-foreground">No barbers yet. Add your first barber.</TableCell>
                      </TableRow>
                    ) : barbers.map((b) => (
                      <TableRow key={b.id} className="border-border hover:bg-accent/30" data-testid={`barber-row-${b.id}`}>
                        <TableCell className="font-medium">{b.name}</TableCell>
                        <TableCell className="text-muted-foreground">{b.email || "—"}</TableCell>
                        <TableCell className="text-muted-foreground">{b.phone || "—"}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="icon" onClick={() => openBarberDialog(b)} data-testid={`edit-barber-${b.id}`}>
                              <Pencil className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-red-400 hover:text-red-300" onClick={() => deleteBarber(b.id)} data-testid={`delete-barber-${b.id}`}>
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ===== SERVICES TAB ===== */}
          <TabsContent value="services" className="mt-6">
            <Card className="bg-card border-border">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-lg">Services</CardTitle>
                <Button onClick={() => openServiceDialog()} data-testid="add-service-btn" size="sm" className="gap-2">
                  <Plus className="w-4 h-4" /> Add Service
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="border-border hover:bg-transparent">
                      <TableHead className="text-muted-foreground">Name</TableHead>
                      <TableHead className="text-muted-foreground">Description</TableHead>
                      <TableHead className="text-muted-foreground">Duration</TableHead>
                      <TableHead className="text-muted-foreground">Price</TableHead>
                      <TableHead className="text-muted-foreground text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      [...Array(3)].map((_, i) => (
                        <TableRow key={i} className="border-border">
                          <TableCell colSpan={5}><div className="h-10 bg-muted/50 animate-pulse rounded" /></TableCell>
                        </TableRow>
                      ))
                    ) : services.length === 0 ? (
                      <TableRow className="border-border">
                        <TableCell colSpan={5} className="text-center py-12 text-muted-foreground">No services yet. Add your first service.</TableCell>
                      </TableRow>
                    ) : services.map((s) => (
                      <TableRow key={s.id} className="border-border hover:bg-accent/30" data-testid={`service-row-${s.id}`}>
                        <TableCell className="font-medium">{s.name}</TableCell>
                        <TableCell className="text-muted-foreground max-w-[200px] truncate">{s.description || "—"}</TableCell>
                        <TableCell><Badge variant="outline">{s.duration_minutes} min</Badge></TableCell>
                        <TableCell className="font-mono text-emerald-400">${s.price.toFixed(2)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="icon" onClick={() => openServiceDialog(s)} data-testid={`edit-service-${s.id}`}>
                              <Pencil className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-red-400 hover:text-red-300" onClick={() => deleteService(s.id)} data-testid={`delete-service-${s.id}`}>
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* ===== BARBER DIALOG ===== */}
        <Dialog open={barberDialogOpen} onOpenChange={setBarberDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingBarber ? "Edit Barber" : "Add Barber"}</DialogTitle>
              <DialogDescription>{editingBarber ? "Update barber details." : "Add a new barber to your shop."}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label>Name *</Label>
                <Input data-testid="barber-name-input" value={barberForm.name} onChange={(e) => setBarberForm({ ...barberForm, name: e.target.value })} placeholder="e.g. Marcus" />
              </div>
              <div>
                <Label>Email</Label>
                <Input data-testid="barber-email-input" value={barberForm.email} onChange={(e) => setBarberForm({ ...barberForm, email: e.target.value })} placeholder="marcus@shop.com" />
              </div>
              <div>
                <Label>Phone</Label>
                <Input data-testid="barber-phone-input" value={barberForm.phone} onChange={(e) => setBarberForm({ ...barberForm, phone: e.target.value })} placeholder="+15551234567" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setBarberDialogOpen(false)}>Cancel</Button>
              <Button onClick={saveBarber} data-testid="save-barber-btn">{editingBarber ? "Update" : "Add Barber"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ===== SERVICE DIALOG ===== */}
        <Dialog open={serviceDialogOpen} onOpenChange={setServiceDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingService ? "Edit Service" : "Add Service"}</DialogTitle>
              <DialogDescription>{editingService ? "Update service details." : "Add a new service to your menu."}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label>Name *</Label>
                <Input data-testid="service-name-input" value={serviceForm.name} onChange={(e) => setServiceForm({ ...serviceForm, name: e.target.value })} placeholder="e.g. Fade Haircut" />
              </div>
              <div>
                <Label>Description</Label>
                <Textarea data-testid="service-desc-input" value={serviceForm.description} onChange={(e) => setServiceForm({ ...serviceForm, description: e.target.value })} placeholder="Optional description" rows={2} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Duration (minutes)</Label>
                  <Input data-testid="service-duration-input" type="number" value={serviceForm.duration_minutes} onChange={(e) => setServiceForm({ ...serviceForm, duration_minutes: e.target.value })} min={5} step={5} />
                </div>
                <div>
                  <Label>Price ($)</Label>
                  <Input data-testid="service-price-input" type="number" value={serviceForm.price} onChange={(e) => setServiceForm({ ...serviceForm, price: e.target.value })} min={0} step={0.01} />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setServiceDialogOpen(false)}>Cancel</Button>
              <Button onClick={saveService} data-testid="save-service-btn">{editingService ? "Update" : "Add Service"}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
}
