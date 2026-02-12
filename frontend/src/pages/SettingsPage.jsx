import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Separator } from "../components/ui/separator";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { 
  Settings, 
  DollarSign, 
  Clock, 
  MessageSquare,
  Save,
  Store,
  Send,
  AlertCircle,
  CalendarDays,
  CreditCard,
  Link2,
  Link2Off,
  CheckCircle2
} from "lucide-react";

export default function SettingsPage() {
  const [shop, setShop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testSMS, setTestSMS] = useState({ phone: "", message: "" });
  const [sendingTest, setSendingTest] = useState(false);
  const [calendarStatus, setCalendarStatus] = useState({ connected: false, email: "" });
  const [connectingCalendar, setConnectingCalendar] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    deposit_amount: 20,
    deposit_required_hours: 48,
    confirmation_window_hours: 24,
    cancellation_window_hours: 4,
    max_messages_per_day: 4,
    retention_enabled: true,
    retention_lapse_weeks: 4,
    retention_cooldown_days: 7,
  });

  useEffect(() => {
    fetchShop();
    fetchCalendarStatus();
    // Check for calendar connection callback
    const params = new URLSearchParams(window.location.search);
    if (params.get("calendar_connected") === "true") {
      toast.success("Google Calendar connected successfully!");
      window.history.replaceState({}, "", "/settings");
      fetchCalendarStatus();
    }
    if (params.get("calendar_error")) {
      toast.error("Failed to connect Google Calendar");
      window.history.replaceState({}, "", "/settings");
    }
  }, []);

  const fetchShop = async () => {
    try {
      const response = await axios.get(`${API}/shop`);
      setShop(response.data);
      setFormData({
        deposit_amount: response.data.deposit_amount,
        deposit_required_hours: response.data.deposit_required_hours,
        confirmation_window_hours: response.data.confirmation_window_hours,
        cancellation_window_hours: response.data.cancellation_window_hours,
        max_messages_per_day: response.data.max_messages_per_day,
        retention_enabled: response.data.retention_enabled ?? true,
        retention_lapse_weeks: response.data.retention_lapse_weeks ?? 4,
        retention_cooldown_days: response.data.retention_cooldown_days ?? 7,
      });
    } catch (error) {
      console.error("Failed to fetch shop:", error);
      toast.error("Failed to load shop settings");
    } finally {
      setLoading(false);
    }
  };

  const fetchCalendarStatus = async () => {
    try {
      const res = await axios.get(`${API}/calendar/status`);
      setCalendarStatus(res.data);
    } catch (error) {
      console.error("Failed to fetch calendar status:", error);
    }
  };

  const connectCalendar = async () => {
    setConnectingCalendar(true);
    try {
      const res = await axios.get(`${API}/oauth/calendar/login`, {
        headers: { "x-origin": window.location.origin }
      });
      if (res.data.authorization_url) {
        window.location.href = res.data.authorization_url;
      }
    } catch (error) {
      toast.error("Failed to initiate Google Calendar connection");
      setConnectingCalendar(false);
    }
  };

  const disconnectCalendar = async () => {
    try {
      await axios.post(`${API}/calendar/disconnect`);
      setCalendarStatus({ connected: false, email: "" });
      toast.success("Google Calendar disconnected");
    } catch (error) {
      toast.error("Failed to disconnect Google Calendar");
    }
  };

  const handleSave = async () => {
    // Client-side validation
    if (formData.deposit_amount < 0) {
      toast.error("Deposit amount must be $0 or more"); return;
    }
    if (formData.deposit_required_hours < 1) {
      toast.error("Deposit required hours must be at least 1"); return;
    }
    if (formData.confirmation_window_hours < 1) {
      toast.error("Confirmation window must be at least 1 hour"); return;
    }
    if (formData.cancellation_window_hours < 0) {
      toast.error("Cancellation window cannot be negative"); return;
    }
    if (formData.max_messages_per_day < 1) {
      toast.error("Max messages per day must be at least 1"); return;
    }

    setSaving(true);
    try {
      await axios.patch(`${API}/shop/policy`, formData);
      toast.success("Settings saved successfully");
      fetchShop();
    } catch (error) {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleSendTestSMS = async () => {
    if (!testSMS.phone || !testSMS.message) {
      toast.error("Please enter phone number and message");
      return;
    }

    setSendingTest(true);
    try {
      await axios.post(`${API}/sms/send-test`, {
        to_phone: testSMS.phone,
        message: testSMS.message
      });
      toast.success("Test SMS sent!");
      setTestSMS({ phone: "", message: "" });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send test SMS");
    } finally {
      setSendingTest(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Settings">
        <div className="space-y-6 animate-pulse">
          <Card className="bg-card border-border">
            <CardContent className="p-6">
              <div className="h-40 bg-muted rounded" />
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Settings">
      <div data-testid="settings-page" className="space-y-6 max-w-4xl">
        {/* Shop Info */}
        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                <Store className="w-5 h-5 text-primary" />
              </div>
              <div>
                <CardTitle className="font-heading">{shop?.name}</CardTitle>
                <CardDescription>{shop?.address}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Phone</p>
                <p className="font-mono">{shop?.phone}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Email</p>
                <p>{shop?.email || "-"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Timezone</p>
                <p>{shop?.timezone}</p>
              </div>
              <div>
                <p className="text-muted-foreground">SMS Consent Link</p>
                <p className="text-primary">/sms-consent</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Policy Settings */}
        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                <Settings className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <CardTitle className="font-heading">Policy Settings</CardTitle>
                <CardDescription>Configure deposit and messaging rules</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Deposit Settings */}
            <div>
              <h4 className="text-sm font-medium mb-4 flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-primary" />
                Deposit Settings
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="deposit_amount">Deposit Amount ($)</Label>
                  <Input
                    id="deposit_amount"
                    data-testid="deposit-amount-input"
                    type="number"
                    step="0.01"
                    min="0"
                    value={formData.deposit_amount}
                    onChange={(e) => setFormData(prev => ({ ...prev, deposit_amount: parseFloat(e.target.value) }))}
                    className="bg-input/50 border-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="deposit_required_hours">
                    Require Deposit (hours before appointment)
                  </Label>
                  <Input
                    id="deposit_required_hours"
                    data-testid="deposit-hours-input"
                    type="number"
                    min="1"
                    value={formData.deposit_required_hours}
                    onChange={(e) => setFormData(prev => ({ ...prev, deposit_required_hours: parseInt(e.target.value) }))}
                    className="bg-input/50 border-input"
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* Timing Settings */}
            <div>
              <h4 className="text-sm font-medium mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-primary" />
                Timing Settings
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="confirmation_window">
                    Confirmation Reminder (hours before)
                  </Label>
                  <Input
                    id="confirmation_window"
                    data-testid="confirmation-hours-input"
                    type="number"
                    min="1"
                    value={formData.confirmation_window_hours}
                    onChange={(e) => setFormData(prev => ({ ...prev, confirmation_window_hours: parseInt(e.target.value) }))}
                    className="bg-input/50 border-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cancellation_window">
                    Minimum Cancellation Notice (hours)
                  </Label>
                  <Input
                    id="cancellation_window"
                    data-testid="cancellation-hours-input"
                    type="number"
                    min="0"
                    value={formData.cancellation_window_hours}
                    onChange={(e) => setFormData(prev => ({ ...prev, cancellation_window_hours: parseInt(e.target.value) }))}
                    className="bg-input/50 border-input"
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* Message Settings */}
            <div>
              <h4 className="text-sm font-medium mb-4 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-primary" />
                Message Rate Limiting
              </h4>
              <div className="space-y-2">
                <Label htmlFor="max_messages">
                  Max Messages Per Day (per client)
                </Label>
                <Input
                  id="max_messages"
                  data-testid="max-messages-input"
                  type="number"
                  min="1"
                  value={formData.max_messages_per_day}
                  onChange={(e) => setFormData(prev => ({ ...prev, max_messages_per_day: parseInt(e.target.value) }))}
                  className="bg-input/50 border-input max-w-xs"
                />
                <p className="text-xs text-muted-foreground">
                  Rate limit for outbound SMS (excludes active conversation replies)
                </p>
              </div>
            </div>

            <Separator />

            {/* Retention Settings */}
            <div>
              <h4 className="text-sm font-medium mb-4 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-primary" />
                Client Retention
              </h4>
              <div className="space-y-4">
                <div className="flex items-center justify-between rounded-lg bg-zinc-800/50 p-3">
                  <div>
                    <p className="text-sm font-medium">Enable Retention Outreach</p>
                    <p className="text-xs text-muted-foreground">Automatically re-engage lapsed clients</p>
                  </div>
                  <Switch
                    data-testid="retention-enabled-switch"
                    checked={formData.retention_enabled}
                    onCheckedChange={(v) => setFormData(prev => ({ ...prev, retention_enabled: v }))}
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="retention_lapse_weeks">
                      Lapse Threshold (weeks since last visit)
                    </Label>
                    <Input
                      id="retention_lapse_weeks"
                      data-testid="retention-lapse-weeks-input"
                      type="number"
                      min="1"
                      max="12"
                      value={formData.retention_lapse_weeks}
                      onChange={(e) => setFormData(prev => ({ ...prev, retention_lapse_weeks: parseInt(e.target.value) }))}
                      className="bg-input/50 border-input"
                      disabled={!formData.retention_enabled}
                    />
                    <p className="text-xs text-muted-foreground">
                      Clients with no visit after this many weeks will receive outreach
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="retention_cooldown_days">
                      Cooldown Period (days between touches)
                    </Label>
                    <Input
                      id="retention_cooldown_days"
                      data-testid="retention-cooldown-input"
                      type="number"
                      min="1"
                      max="30"
                      value={formData.retention_cooldown_days}
                      onChange={(e) => setFormData(prev => ({ ...prev, retention_cooldown_days: parseInt(e.target.value) }))}
                      className="bg-input/50 border-input"
                      disabled={!formData.retention_enabled}
                    />
                    <p className="text-xs text-muted-foreground">
                      Minimum days between outreach messages to the same client
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                onClick={handleSave}
                disabled={saving}
                data-testid="save-settings-button"
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                <Save className="w-4 h-4 mr-2" />
                {saving ? "Saving..." : "Save Settings"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Integrations */}
        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-indigo-500/10 rounded-lg flex items-center justify-center">
                <Link2 className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <CardTitle className="font-heading">Integrations</CardTitle>
                <CardDescription>Connected external services</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Stripe */}
            <div className="flex items-center justify-between rounded-lg bg-zinc-800/50 p-4" data-testid="stripe-integration-card">
              <div className="flex items-center gap-3">
                <CreditCard className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="text-sm font-medium">Stripe Payments</p>
                  <p className="text-xs text-muted-foreground">Deposit collection & payment processing</p>
                </div>
              </div>
              <Badge className="bg-emerald-500/20 text-emerald-400" data-testid="stripe-status-badge">
                <CheckCircle2 className="w-3 h-3 mr-1" /> Active
              </Badge>
            </div>

            {/* Google Calendar */}
            <div className="flex items-center justify-between rounded-lg bg-zinc-800/50 p-4" data-testid="gcal-integration-card">
              <div className="flex items-center gap-3">
                <CalendarDays className="w-5 h-5 text-blue-400" />
                <div>
                  <p className="text-sm font-medium">Google Calendar</p>
                  <p className="text-xs text-muted-foreground">
                    {calendarStatus.connected
                      ? `Connected as ${calendarStatus.email}`
                      : "Sync appointments to your calendar"}
                  </p>
                </div>
              </div>
              {calendarStatus.connected ? (
                <div className="flex items-center gap-2">
                  <Badge className="bg-emerald-500/20 text-emerald-400" data-testid="gcal-status-badge">
                    <CheckCircle2 className="w-3 h-3 mr-1" /> Connected
                  </Badge>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={disconnectCalendar}
                    className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    data-testid="disconnect-calendar-btn"
                  >
                    <Link2Off className="w-4 h-4" />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={connectCalendar}
                  disabled={connectingCalendar}
                  data-testid="connect-calendar-btn"
                  className="gap-1"
                >
                  <Link2 className="w-4 h-4" />
                  {connectingCalendar ? "Connecting..." : "Connect"}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Test SMS */}
        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-emerald-500/10 rounded-lg flex items-center justify-center">
                <Send className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <CardTitle className="font-heading">Send Test SMS</CardTitle>
                <CardDescription>
                  Test your Twilio integration (requires TWILIO_ENABLED=true)
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-400 shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-yellow-400">SMS is currently in simulation mode</p>
                <p className="text-muted-foreground">
                  Set TWILIO_ENABLED=true and configure your Twilio credentials to send real SMS.
                </p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="test_phone">Phone Number</Label>
                <Input
                  id="test_phone"
                  data-testid="test-sms-phone"
                  placeholder="+1234567890"
                  value={testSMS.phone}
                  onChange={(e) => setTestSMS(prev => ({ ...prev, phone: e.target.value }))}
                  className="bg-input/50 border-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="test_message">Message</Label>
                <Input
                  id="test_message"
                  data-testid="test-sms-message"
                  placeholder="Test message from Barbershop Autopilot"
                  value={testSMS.message}
                  onChange={(e) => setTestSMS(prev => ({ ...prev, message: e.target.value }))}
                  className="bg-input/50 border-input"
                />
              </div>
            </div>
            
            <Button
              onClick={handleSendTestSMS}
              disabled={sendingTest}
              data-testid="send-test-sms-button"
              variant="outline"
            >
              <Send className="w-4 h-4 mr-2" />
              {sendingTest ? "Sending..." : "Send Test SMS"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
