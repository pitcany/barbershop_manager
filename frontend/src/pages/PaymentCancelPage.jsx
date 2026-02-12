import { useSearchParams, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { XCircle, ArrowLeft } from "lucide-react";

export default function PaymentCancelPage() {
  const [searchParams] = useSearchParams();
  const appointmentId = searchParams.get("appointment_id");

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4" data-testid="payment-cancel-page">
      <Card className="max-w-md w-full bg-[#12121a] border-[#1e1e2e]">
        <CardHeader className="text-center space-y-4">
          <div className="flex justify-center">
            <XCircle className="w-12 h-12 text-red-400" />
          </div>
          <CardTitle className="text-xl text-zinc-100" data-testid="payment-cancel-message">
            Payment Cancelled
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          <p className="text-zinc-400">
            Your deposit payment was not completed. Your appointment still requires a deposit to be confirmed.
          </p>
          <div className="pt-4">
            <Link to="/appointments">
              <Button variant="outline" className="gap-2" data-testid="back-to-appointments-cancel">
                <ArrowLeft className="w-4 h-4" /> Back to Appointments
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
