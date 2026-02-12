import { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import axios from "axios";
import { API } from "../App";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { CheckCircle, Clock, AlertTriangle, ArrowLeft } from "lucide-react";

export default function PaymentSuccessPage() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const appointmentId = searchParams.get("appointment_id");
  const [status, setStatus] = useState("checking");
  const [paymentData, setPaymentData] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const maxAttempts = 8;

  const pollStatus = useCallback(async () => {
    if (!sessionId) {
      setStatus("error");
      return;
    }

    try {
      const res = await axios.get(`${API}/payments/status/${sessionId}`);
      setPaymentData(res.data);

      if (res.data.payment_status === "paid") {
        setStatus("paid");
        return;
      }
      if (res.data.status === "expired") {
        setStatus("expired");
        return;
      }
      setStatus("processing");
      setAttempts((prev) => prev + 1);
    } catch {
      setStatus("error");
    }
  }, [sessionId]);

  useEffect(() => {
    pollStatus();
  }, [pollStatus]);

  useEffect(() => {
    if (status === "processing" && attempts < maxAttempts) {
      const timer = setTimeout(pollStatus, 2500);
      return () => clearTimeout(timer);
    }
    if (attempts >= maxAttempts && status === "processing") {
      setStatus("timeout");
    }
  }, [status, attempts, pollStatus]);

  const icons = {
    checking: <Clock className="w-12 h-12 text-amber-400 animate-pulse" />,
    processing: <Clock className="w-12 h-12 text-amber-400 animate-pulse" />,
    paid: <CheckCircle className="w-12 h-12 text-emerald-400" />,
    expired: <AlertTriangle className="w-12 h-12 text-red-400" />,
    timeout: <AlertTriangle className="w-12 h-12 text-amber-400" />,
    error: <AlertTriangle className="w-12 h-12 text-red-400" />,
  };

  const messages = {
    checking: "Verifying your payment...",
    processing: "Payment is being processed...",
    paid: "Payment successful!",
    expired: "Payment session expired",
    timeout: "Payment verification timed out. Please check your appointment status.",
    error: "Unable to verify payment",
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4" data-testid="payment-success-page">
      <Card className="max-w-md w-full bg-[#12121a] border-[#1e1e2e]">
        <CardHeader className="text-center space-y-4">
          <div className="flex justify-center">{icons[status]}</div>
          <CardTitle className="text-xl text-zinc-100" data-testid="payment-status-message">
            {messages[status]}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          {paymentData?.amount && status === "paid" && (
            <p className="text-zinc-400" data-testid="payment-amount">
              Deposit of <span className="text-emerald-400 font-semibold">${paymentData.amount.toFixed(2)}</span> received
            </p>
          )}
          {appointmentId && status === "paid" && (
            <p className="text-sm text-zinc-500">
              Your appointment has been confirmed.
            </p>
          )}
          <div className="pt-4">
            <Link to="/appointments">
              <Button variant="outline" className="gap-2" data-testid="back-to-appointments">
                <ArrowLeft className="w-4 h-4" /> Back to Appointments
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
