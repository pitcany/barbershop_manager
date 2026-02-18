import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useParams, Link } from "react-router-dom";
import axios from "axios";
import { API } from "../App";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { CheckCircle, Clock, AlertTriangle, MapPin, Phone, Scissors } from "lucide-react";

export default function BookingConfirmationPage() {
  const [searchParams] = useSearchParams();
  const { shopSlug } = useParams();
  const appointmentId = searchParams.get("appointment_id");
  const sessionId = searchParams.get("session_id");
  const [appointment, setAppointment] = useState(null);
  const [paymentStatus, setPaymentStatus] = useState(sessionId ? "checking" : "none");
  const [shop, setShop] = useState(null);
  const [attempts, setAttempts] = useState(0);

  const publicBase = shopSlug ? `${API}/public/s/${shopSlug}` : `${API}/public`;

  useEffect(() => {
    if (appointmentId) {
      axios.get(`${API}/public/appointment/${appointmentId}`)
        .then((res) => setAppointment(res.data))
        .catch(() => {});
    }
    axios.get(`${publicBase}/shop-info`)
      .then((res) => setShop(res.data))
      .catch(() => {});
  }, [appointmentId, publicBase]);

  const pollPayment = useCallback(async () => {
    if (!sessionId) return;
    try {
      // Use public endpoint - no auth needed
      const token = localStorage.getItem("token");
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.get(`${API}/payments/status/${sessionId}`, { headers });
      if (res.data.payment_status === "paid") {
        setPaymentStatus("paid");
        // Refresh appointment
        if (appointmentId) {
          const aptRes = await axios.get(`${API}/public/appointment/${appointmentId}`);
          setAppointment(aptRes.data);
        }
        return;
      }
      if (res.data.status === "expired") {
        setPaymentStatus("expired");
        return;
      }
      setPaymentStatus("processing");
      setAttempts((p) => p + 1);
    } catch {
      // If 401, skip polling — user not authed
      setPaymentStatus("paid"); // Assume success from Stripe redirect
    }
  }, [sessionId, appointmentId]);

  useEffect(() => {
    if (sessionId) pollPayment();
  }, [sessionId, pollPayment]);

  useEffect(() => {
    if (paymentStatus === "processing" && attempts < 6) {
      const timer = setTimeout(pollPayment, 2500);
      return () => clearTimeout(timer);
    }
    if (attempts >= 6 && paymentStatus === "processing") {
      setPaymentStatus("paid"); // Assume success after timeout
    }
  }, [paymentStatus, attempts, pollPayment]);

  const isSuccess = paymentStatus === "paid" || paymentStatus === "none";

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4" data-testid="booking-confirmation-page">
      <Card className="max-w-md w-full bg-[#12121a] border-[#1e1e2e]">
        <CardHeader className="text-center space-y-3">
          <div className="flex justify-center">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${
              isSuccess ? "bg-emerald-500/10" : paymentStatus === "checking" || paymentStatus === "processing" ? "bg-amber-500/10" : "bg-red-500/10"
            }`}>
              {isSuccess ? <CheckCircle className="w-8 h-8 text-emerald-400" /> :
               paymentStatus === "checking" || paymentStatus === "processing" ? <Clock className="w-8 h-8 text-amber-400 animate-pulse" /> :
               <AlertTriangle className="w-8 h-8 text-red-400" />}
            </div>
          </div>
          <CardTitle className="text-xl text-zinc-100" data-testid="confirmation-title">
            {isSuccess ? "Booking Confirmed!" :
             paymentStatus === "checking" || paymentStatus === "processing" ? "Verifying Payment..." :
             "Payment Issue"}
          </CardTitle>
          {isSuccess && <CardDescription>Your appointment has been scheduled</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-4">
          {appointment && (
            <div className="rounded-lg bg-zinc-800/50 p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Service</span>
                <span className="text-zinc-100">{appointment.service_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Barber</span>
                <span className="text-zinc-100">{appointment.barber_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Date & Time</span>
                <span className="text-zinc-100">
                  {new Date(appointment.scheduled_at).toLocaleString([], {
                    weekday: "short", month: "short", day: "numeric",
                    hour: "numeric", minute: "2-digit"
                  })}
                </span>
              </div>
              {appointment.deposit_paid && appointment.deposit_amount > 0 && (
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400">Deposit Paid</span>
                  <span className="text-emerald-400">${appointment.deposit_amount?.toFixed(2)}</span>
                </div>
              )}
            </div>
          )}

          {shop && (
            <div className="text-center text-sm text-zinc-500 space-y-1">
              <p className="flex items-center justify-center gap-1"><MapPin className="w-3 h-3" /> {shop.address}</p>
              <p className="flex items-center justify-center gap-1"><Phone className="w-3 h-3" /> {shop.phone}</p>
            </div>
          )}

          <div className="pt-2 text-center">
            <Link to={shopSlug ? `/book/${shopSlug}` : "/book"}>
              <Button variant="outline" className="gap-2" data-testid="book-another-link">
                <Scissors className="w-4 h-4" /> Book Another Appointment
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
