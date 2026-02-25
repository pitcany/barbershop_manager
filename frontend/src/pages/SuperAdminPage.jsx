import { useState, useEffect } from "react";
import axios from "axios";
import { API, useAuth } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
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
import { toast } from "sonner";
import {
  Plus,
  Users,
  Copy,
  ExternalLink,
  ChevronRight,
  Building2,
  UserPlus,
  Eye,
  EyeOff,
  Calendar,
  DollarSign,
  AlertTriangle,
  TrendingUp,
  Database,
  Trash2,
  Loader2,
} from "lucide-react";

export default function SuperAdminPage() {
  const { user } = useAuth();
  const [shops, setShops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [platformStats, setPlatformStats] = useState(null);

  // Create shop dialog
  const [shopDialogOpen, setShopDialogOpen] = useState(false);
  const [shopForm, setShopForm] = useState({
    name: "", slug: "", phone: "", email: "", address: "", timezone: "America/New_York",
  });
  const [submittingShop, setSubmittingShop] = useState(false);

  // Shop detail panel
  const [selectedShop, setSelectedShop] = useState(null);
  const [shopAdmins, setShopAdmins] = useState([]);
  const [loadingAdmins, setLoadingAdmins] = useState(false);

  // Create admin dialog
  const [adminDialogOpen, setAdminDialogOpen] = useState(false);
  const [adminForm, setAdminForm] = useState({ username: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [submittingAdmin, setSubmittingAdmin] = useState(false);

  // Demo data
  const [seedingDemo, setSeedingDemo] = useState(false);
  const [clearingData, setClearingData] = useState(false);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [shopsRes, statsRes] = await Promise.all([
        axios.get(`${API}/admin/shops`),
        axios.get(`${API}/admin/platform-stats`),
      ]);
      setShops(shopsRes.data.shops);
      setPlatformStats(statsRes.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load data");
    } finally { setLoading(false); }
  };

  const fetchShops = async () => {
    try {
      const res = await axios.get(`${API}/admin/shops`);
      setShops(res.data.shops);
    } catch {}
  };

  // ===== CREATE SHOP =====
  const openShopDialog = () => {
    setShopForm({ name: "", slug: "", phone: "", email: "", address: "", timezone: "America/New_York" });
    setShopDialogOpen(true);
  };

  const autoSlug = (name) => {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50);
  };

  const handleCreateShop = async () => {
    if (!shopForm.name.trim() || !shopForm.slug.trim() || !shopForm.phone.trim()) {
      toast.error("Name, slug, and phone are required");
      return;
    }
    setSubmittingShop(true);
    try {
      await axios.post(`${API}/admin/shops`, shopForm);
      toast.success("Shop created successfully");
      setShopDialogOpen(false);
      fetchData();
    } catch (e) {
      const detail = e.response?.data?.detail;
      // Handle Pydantic validation errors (array of objects) vs simple string errors
      const errMsg = Array.isArray(detail)
        ? detail.map(d => d.msg || d.message || JSON.stringify(d)).join("; ")
        : (typeof detail === "string" ? detail : "Failed to create shop");
      toast.error(errMsg);
    } finally { setSubmittingShop(false); }
  };

  // ===== SHOP DETAIL =====
  const selectShop = async (shop) => {
    setSelectedShop(shop);
    setLoadingAdmins(true);
    try {
      const res = await axios.get(`${API}/admin/shops/${shop.id}/admins`);
      setShopAdmins(res.data.admins);
    } catch { toast.error("Failed to load admins"); }
    finally { setLoadingAdmins(false); }
  };

  // ===== CREATE ADMIN =====
  const openAdminDialog = () => {
    setAdminForm({ username: "", password: "" });
    setShowPassword(false);
    setAdminDialogOpen(true);
  };

  const handleCreateAdmin = async () => {
    if (!adminForm.username.trim() || !adminForm.password.trim()) {
      toast.error("Username and password are required");
      return;
    }
    setSubmittingAdmin(true);
    try {
      await axios.post(`${API}/admin/shops/${selectedShop.id}/admins`, adminForm);
      toast.success("Admin created");
      setAdminDialogOpen(false);
      selectShop(selectedShop);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const errMsg = Array.isArray(detail)
        ? detail.map(d => d.msg || d.message || JSON.stringify(d)).join("; ")
        : (typeof detail === "string" ? detail : "Failed to create admin");
      toast.error(errMsg);
    } finally { setSubmittingAdmin(false); }
  };

  const copyBookingLink = (slug) => {
    const link = `${window.location.origin}/book/${slug}`;
    navigator.clipboard.writeText(link).then(() => toast.success("Booking link copied!")).catch(() => toast.error("Failed to copy"));
  };

  const handleSeedDemo = async () => {
    if (!selectedShop) return;
    setSeedingDemo(true);
    try {
      const res = await axios.post(`${API}/admin/shops/${selectedShop.id}/seed-demo`);
      toast.success(res.data.message);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to seed demo data"); }
    finally { setSeedingDemo(false); }
  };

  const handleClearData = async () => {
    if (!selectedShop) return;
    setClearingData(true);
    try {
      const res = await axios.post(`${API}/admin/shops/${selectedShop.id}/clear-data`);
      toast.success(res.data.message);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to clear data"); }
    finally { setClearingData(false); }
  };

  if (user?.role !== "super_admin") {
    return (
      <Layout title="Access Denied">
        <Card className="bg-card border-border">
          <CardContent className="p-12 text-center text-muted-foreground">
            You don't have permission to access this page.
          </CardContent>
        </Card>
      </Layout>
    );
  }

  return (
    <Layout title="Platform Admin">
      <div data-testid="super-admin-page" className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-muted-foreground text-sm">Manage all barbershops on the platform</p>
          </div>
          <Button onClick={openShopDialog} data-testid="create-shop-btn" className="gap-2">
            <Plus className="w-4 h-4" /> New Shop
          </Button>
        </div>

        {/* Platform Overview Stats */}
        {platformStats && (
          <div data-testid="platform-overview" className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                    <Building2 className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Total Shops</p>
                    <p className="text-2xl font-mono font-semibold" data-testid="stat-total-shops">{platformStats.total_shops}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                    <Calendar className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Appointments (30d)</p>
                    <p className="text-2xl font-mono font-semibold" data-testid="stat-month-appointments">{platformStats.month_appointments}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-emerald-500/10 rounded-lg flex items-center justify-center">
                    <DollarSign className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Revenue (30d)</p>
                    <p className="text-2xl font-mono font-semibold text-emerald-400" data-testid="stat-month-revenue">${platformStats.month_revenue.toFixed(2)}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${platformStats.no_show_rate > 10 ? "bg-red-500/10" : "bg-yellow-500/10"}`}>
                    <AlertTriangle className={`w-5 h-5 ${platformStats.no_show_rate > 10 ? "text-red-400" : "text-yellow-400"}`} />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">No-Show Rate</p>
                    <p className="text-2xl font-mono font-semibold" data-testid="stat-no-show-rate">{platformStats.no_show_rate}%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Per-Shop Breakdown */}
        {platformStats?.shop_breakdown?.length > 1 && (
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" /> Shop Performance (30 days)
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="text-muted-foreground">Shop</TableHead>
                    <TableHead className="text-muted-foreground text-right">Clients</TableHead>
                    <TableHead className="text-muted-foreground text-right">Appointments</TableHead>
                    <TableHead className="text-muted-foreground text-right">No-Shows</TableHead>
                    <TableHead className="text-muted-foreground text-right">Revenue</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {platformStats.shop_breakdown.map((s) => (
                    <TableRow key={s.id} className="border-border hover:bg-accent/30" data-testid={`breakdown-row-${s.id}`}>
                      <TableCell>
                        <p className="font-medium">{s.name}</p>
                        <p className="text-xs text-muted-foreground font-mono">/{s.slug}</p>
                      </TableCell>
                      <TableCell className="text-right font-mono">{s.total_clients}</TableCell>
                      <TableCell className="text-right font-mono">{s.month_appointments}</TableCell>
                      <TableCell className="text-right">
                        <Badge className={s.no_show_rate > 10 ? "bg-red-500/20 text-red-400" : "bg-yellow-500/20 text-yellow-400"}>
                          {s.month_no_shows} ({s.no_show_rate}%)
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-emerald-400">${s.month_revenue.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Shop List */}
          <div className="lg:col-span-1 space-y-3">
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Shops ({shops.length})</h3>
            {loading ? (
              [...Array(3)].map((_, i) => (
                <Card key={i} className="bg-card border-border animate-pulse">
                  <CardContent className="p-4"><div className="h-16 bg-muted/50 rounded" /></CardContent>
                </Card>
              ))
            ) : shops.length === 0 ? (
              <Card className="bg-card border-border">
                <CardContent className="p-8 text-center text-muted-foreground">
                  No shops yet. Create your first shop.
                </CardContent>
              </Card>
            ) : shops.map((shop) => (
              <Card
                key={shop.id}
                data-testid={`shop-card-${shop.id}`}
                className={`bg-card border-border cursor-pointer transition-all hover:border-primary/50 ${selectedShop?.id === shop.id ? "border-primary ring-1 ring-primary/30" : ""}`}
                onClick={() => selectShop(shop)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="font-medium truncate">{shop.name}</p>
                      <p className="text-xs text-muted-foreground font-mono">/{shop.slug}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="outline" className="text-xs">
                        <Users className="w-3 h-3 mr-1" />{shop.admin_count || 0}
                      </Badge>
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Shop Detail Panel */}
          <div className="lg:col-span-2">
            {!selectedShop ? (
              <Card className="bg-card border-border h-full">
                <CardContent className="p-12 text-center text-muted-foreground flex flex-col items-center justify-center h-full">
                  <Building2 className="w-12 h-12 mb-4 opacity-30" />
                  <p>Select a shop to view details</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-6">
                {/* Shop Info */}
                <Card className="bg-card border-border">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-xl">{selectedShop.name}</CardTitle>
                        <CardDescription className="font-mono">/{selectedShop.slug}</CardDescription>
                      </div>
                      <Button variant="outline" size="sm" className="gap-2" onClick={() => copyBookingLink(selectedShop.slug)} data-testid="copy-shop-booking-link">
                        <Copy className="w-3.5 h-3.5" /> Copy Booking Link
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground text-xs mb-1">Phone</p>
                        <p className="font-mono">{selectedShop.phone}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs mb-1">Email</p>
                        <p>{selectedShop.email || "—"}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs mb-1">Address</p>
                        <p>{selectedShop.address || "—"}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs mb-1">Timezone</p>
                        <p className="font-mono text-xs">{selectedShop.timezone}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs mb-1">Deposit Amount</p>
                        <p className="font-mono text-emerald-400">${selectedShop.deposit_amount}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground text-xs mb-1">Booking Link</p>
                        <a
                          href={`${window.location.origin}/book/${selectedShop.slug}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary hover:underline flex items-center gap-1 text-xs"
                          data-testid="shop-booking-link"
                        >
                          /book/{selectedShop.slug} <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Admins */}
                <Card className="bg-card border-border">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-lg">Shop Admins</CardTitle>
                    <Button onClick={openAdminDialog} size="sm" className="gap-2" data-testid="create-admin-btn">
                      <UserPlus className="w-4 h-4" /> Add Admin
                    </Button>
                  </CardHeader>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-border hover:bg-transparent">
                          <TableHead className="text-muted-foreground">Username</TableHead>
                          <TableHead className="text-muted-foreground">Role</TableHead>
                          <TableHead className="text-muted-foreground">Created</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {loadingAdmins ? (
                          <TableRow className="border-border">
                            <TableCell colSpan={3}><div className="h-10 bg-muted/50 animate-pulse rounded" /></TableCell>
                          </TableRow>
                        ) : shopAdmins.length === 0 ? (
                          <TableRow className="border-border">
                            <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">No admins. Add one to give access.</TableCell>
                          </TableRow>
                        ) : shopAdmins.map((admin) => (
                          <TableRow key={admin.id} className="border-border hover:bg-accent/30" data-testid={`admin-row-${admin.id}`}>
                            <TableCell className="font-medium">{admin.username}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className={admin.role === "super_admin" ? "border-primary text-primary" : ""}>
                                {admin.role}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">
                              {admin.created_at ? new Date(admin.created_at).toLocaleDateString() : "—"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>

        {/* ===== CREATE SHOP DIALOG ===== */}
        <Dialog open={shopDialogOpen} onOpenChange={setShopDialogOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Create New Shop</DialogTitle>
              <DialogDescription>Add a new barbershop to the platform.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label>Shop Name *</Label>
                <Input
                  data-testid="new-shop-name"
                  value={shopForm.name}
                  onChange={(e) => {
                    const name = e.target.value;
                    setShopForm(f => ({ ...f, name, slug: autoSlug(name) }));
                  }}
                  placeholder="e.g. Classic Cuts Downtown"
                />
              </div>
              <div>
                <Label>Slug *</Label>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-sm">/book/</span>
                  <Input
                    data-testid="new-shop-slug"
                    value={shopForm.slug}
                    onChange={(e) => setShopForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") }))}
                    placeholder="classic-cuts-downtown"
                    className="font-mono"
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">URL-safe identifier. Lowercase, hyphens only.</p>
              </div>
              <div>
                <Label>Phone * (E.164 format)</Label>
                <Input
                  data-testid="new-shop-phone"
                  value={shopForm.phone}
                  onChange={(e) => setShopForm(f => ({ ...f, phone: e.target.value }))}
                  placeholder="+15551234567"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Email</Label>
                  <Input
                    data-testid="new-shop-email"
                    value={shopForm.email}
                    onChange={(e) => setShopForm(f => ({ ...f, email: e.target.value }))}
                    placeholder="shop@example.com"
                  />
                </div>
                <div>
                  <Label>Timezone</Label>
                  <Input
                    data-testid="new-shop-timezone"
                    value={shopForm.timezone}
                    onChange={(e) => setShopForm(f => ({ ...f, timezone: e.target.value }))}
                    placeholder="America/New_York"
                  />
                </div>
              </div>
              <div>
                <Label>Address</Label>
                <Input
                  data-testid="new-shop-address"
                  value={shopForm.address}
                  onChange={(e) => setShopForm(f => ({ ...f, address: e.target.value }))}
                  placeholder="123 Main St, City, ST 12345"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShopDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleCreateShop} disabled={submittingShop} data-testid="submit-create-shop">
                {submittingShop ? "Creating..." : "Create Shop"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ===== CREATE ADMIN DIALOG ===== */}
        <Dialog open={adminDialogOpen} onOpenChange={setAdminDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Admin for {selectedShop?.name}</DialogTitle>
              <DialogDescription>Create login credentials for this shop's manager.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label>Username *</Label>
                <Input
                  data-testid="new-admin-username"
                  value={adminForm.username}
                  onChange={(e) => setAdminForm(f => ({ ...f, username: e.target.value }))}
                  placeholder="e.g. john_manager"
                />
              </div>
              <div>
                <Label>Password *</Label>
                <div className="relative">
                  <Input
                    data-testid="new-admin-password"
                    type={showPassword ? "text" : "password"}
                    value={adminForm.password}
                    onChange={(e) => setAdminForm(f => ({ ...f, password: e.target.value }))}
                    placeholder="Minimum 8 characters"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                    onClick={() => setShowPassword(p => !p)}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAdminDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleCreateAdmin} disabled={submittingAdmin} data-testid="submit-create-admin">
                {submittingAdmin ? "Creating..." : "Create Admin"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
}
