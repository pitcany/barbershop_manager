import { useState, useEffect } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Checkbox } from "../components/ui/checkbox";
import { toast } from "sonner";
import { Scissors, Phone, User, CheckCircle, MessageSquare } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export default function SMSConsentPage() {
  const [formData, setFormData] = useState({
    name: "",
    phone: "",
    consent: false
  });
  const [shopInfo, setShopInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    fetchShopInfo();
  }, []);

  const fetchShopInfo = async () => {
    try {
      const response = await axios.get(`${API}/public/shop-info`);
      setShopInfo(response.data);
    } catch (error) {
      console.error("Failed to fetch shop info:", error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.consent) {
      toast.error("Please agree to receive SMS notifications");
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${API}/public/sms-consent`, formData);
      setSubmitted(true);
      toast.success("Consent recorded successfully!");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to submit consent");
    } finally {
      setLoading(false);
    }
  };

  const formatPhone = (value) => {
    // Remove all non-digits
    const digits = value.replace(/\D/g, "");
    
    // Add +1 if US number
    if (digits.length === 10) {
      return `+1${digits}`;
    }
    
    // If starts with 1 and is 11 digits
    if (digits.length === 11 && digits.startsWith("1")) {
      return `+${digits}`;
    }
    
    // Return with + if not already there
    if (value.startsWith("+")) {
      return value;
    }
    
    return `+${digits}`;
  };

  if (submitted) {
    return (
      <div 
        className="min-h-screen flex items-center justify-center p-4"
        style={{ backgroundColor: '#09090b' }}
      >
        <Card className="w-full max-w-md bg-card border-border text-center">
          <CardContent className="p-8">
            <div className="w-20 h-20 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="w-10 h-10 text-emerald-400" />
            </div>
            <h2 className="font-heading text-2xl font-bold mb-2 text-foreground">
              You're All Set!
            </h2>
            <p className="text-muted-foreground mb-6">
              You'll now receive appointment reminders and updates via SMS from {shopInfo?.name || "our barbershop"}.
            </p>
            <div className="p-4 bg-secondary/50 rounded-lg text-sm text-muted-foreground">
              <p className="flex items-center justify-center gap-2">
                <MessageSquare className="w-4 h-4" />
                Text STOP anytime to opt out
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div 
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        backgroundImage: `linear-gradient(to bottom, rgba(9, 9, 11, 0.9), rgba(9, 9, 11, 0.98)), url('https://images.unsplash.com/photo-1758887260983-c171388cf56f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwxfHxiYXJiZXIlMjB0b29scyUyMHNjaXNzb3JzJTIwY2xpcHBlcnN8ZW58MHx8fHwxNzcwNDA0NTA3fDA&ixlib=rb-4.1.0&q=85')`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      }}
    >
      <Card className="w-full max-w-md bg-card/95 backdrop-blur-sm border-border">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
            <Scissors className="w-8 h-8 text-primary" />
          </div>
          <div>
            <CardTitle className="font-heading text-2xl font-bold tracking-tight text-foreground">
              {shopInfo?.name || "Barbershop"}
            </CardTitle>
            <CardDescription className="text-muted-foreground mt-2">
              Sign up for SMS appointment reminders
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-sm font-medium text-foreground">
                Your Name
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="name"
                  data-testid="consent-name-input"
                  type="text"
                  placeholder="Enter your name"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  className="pl-10 bg-input/50 border-input focus:ring-primary focus:border-primary"
                  required
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="phone" className="text-sm font-medium text-foreground">
                Phone Number
              </Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="phone"
                  data-testid="consent-phone-input"
                  type="tel"
                  placeholder="+1 (555) 123-4567"
                  value={formData.phone}
                  onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                  onBlur={(e) => {
                    if (e.target.value) {
                      setFormData(prev => ({ ...prev, phone: formatPhone(e.target.value) }));
                    }
                  }}
                  className="pl-10 bg-input/50 border-input focus:ring-primary focus:border-primary"
                  required
                />
              </div>
              <p className="text-xs text-muted-foreground">
                We'll use this number to send appointment reminders
              </p>
            </div>

            <div className="flex items-start space-x-3 p-4 bg-secondary/30 rounded-lg">
              <Checkbox
                id="consent"
                data-testid="consent-checkbox"
                checked={formData.consent}
                onCheckedChange={(checked) => setFormData(prev => ({ ...prev, consent: checked }))}
              />
              <div className="text-sm">
                <Label htmlFor="consent" className="font-normal text-foreground cursor-pointer">
                  I agree to receive SMS appointment reminders and updates
                </Label>
                <p className="text-xs text-muted-foreground mt-1">
                  Message & data rates may apply. Reply STOP to opt out anytime.
                </p>
              </div>
            </div>

            <Button
              type="submit"
              data-testid="consent-submit-button"
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90 font-medium"
              disabled={loading || !formData.consent}
            >
              {loading ? "Submitting..." : "Sign Up for SMS"}
            </Button>
          </form>

          {shopInfo?.phone && (
            <p className="text-xs text-muted-foreground text-center mt-6">
              Questions? Call us at {shopInfo.phone}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
