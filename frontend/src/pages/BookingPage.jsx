import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../App";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import {
  Scissors, User, Clock, Calendar, ChevronRight, ChevronLeft,
  CheckCircle, CreditCard, MapPin, Phone, AlertTriangle
} from "lucide-react";

const STEPS = ["service", "barber", "datetime", "info", "confirm"];

export default function BookingPage() {
  const [searchParams] = useSearchParams();
  const { shopSlug: urlSlug } = useParams();
  const navigate = useNavigate();
  const [shopSlug, setShopSlug] = useState(urlSlug || "");
  const [shop, setShop] = useState(null);
  const [services, setServices] = useState([]);
  const [barbers, setBarbers] = useState([]);
  const [slots, setSlots] = useState([]);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [booking, setBooking] = useState(false);
  const [bookingResult, setBookingResult] = useState(null);
  const [error, setError] = useState("");

  const [selected, setSelected] = useState({
    service: null,
    barber: null,
    date: "",
    slot: null,
    name: "",
    phone: "",
    email: "",
    notes: "",
    sms_consent: true,
  });

  // Build API base path: slug-based when available, fallback otherwise
  const publicBase = shopSlug ? `${API}/public/s/${shopSlug}` : `${API}/public`;

  useEffect(() => {
    // Compute base from URL param directly to avoid depending on mutable shopSlug state
    const base = urlSlug ? `${API}/public/s/${urlSlug}` : `${API}/public`;
    Promise.all([
      axios.get(`${base}/shop-info`),
      axios.get(`${base}/services`),
      axios.get(`${base}/barbers`),
    ]).then(([shopRes, svcRes, barberRes]) => {
      setShop(shopRes.data);
      setServices(svcRes.data.services || []);
      setBarbers(barberRes.data.barbers || []);
      // If we didn't have a slug from URL, redirect to the slug-based URL
      if (!urlSlug && shopRes.data.slug) {
        navigate(`/book/${shopRes.data.slug}`, { replace: true });
      }
    }).catch(() => setError("Unable to load booking info"))
      .finally(() => setLoading(false));
  }, [urlSlug, navigate]);

  // Check for payment cancellation
  useEffect(() => {
    if (searchParams.get("payment_cancelled") === "true") {
      setError("Payment was cancelled. You can try booking again.");
    }
  }, [searchParams]);

  const fetchSlots = useCallback(async (date) => {
    if (!date || !selected.service) return;
    setSlotsLoading(true);
    try {
      const params = new URLSearchParams({
        date: `${date}T00:00:00`,
        service_id: selected.service.id,
      });
      if (selected.barber) params.set("barber_id", selected.barber.id);
      const res = await axios.get(`${publicBase}/availability?${params}`);
      setSlots(res.data.slots || []);
    } catch {
      setSlots([]);
    } finally {
      setSlotsLoading(false);
    }
  }, [selected.service, selected.barber, publicBase]);

  useEffect(() => {
    if (selected.date) fetchSlots(selected.date);
  }, [selected.date, fetchSlots]);

  const handleBook = async () => {
    setBooking(true);
    setError("");
    try {
      const res = await axios.post(`${publicBase}/book`, {
        name: selected.name,
        phone: selected.phone,
        email: selected.email,
        barber_id: (selected.barber || { id: selected.slot.barber_id }).id,
        service_id: selected.service.id,
        scheduled_at: selected.slot.start,
        notes: selected.notes,
        sms_consent: selected.sms_consent,
      }, { headers: { "x-origin": window.location.origin } });

      setBookingResult(res.data);

      // If deposit required and checkout URL, redirect to Stripe
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
        return;
      }
      setStep(STEPS.length); // Go to confirmation
    } catch (err) {
      setError(err.response?.data?.detail || "Booking failed. Please try again.");
    } finally {
      setBooking(false);
    }
  };

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  // Generate next 14 days for date selection
  const dates = Array.from({ length: 14 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    return d.toISOString().slice(0, 10);
  });

  const formatSlotTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  };

  const formatDate = (str) => {
    const d = new Date(str + "T12:00:00");
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  };

  // Group slots by barber for display
  const slotsByBarber = slots.reduce((acc, s) => {
    const key = s.barber_name;
    if (!acc[key]) acc[key] = [];
    acc[key].push(s);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="animate-pulse text-zinc-400">Loading...</div>
      </div>
    );
  }

  // Confirmation screen (after successful booking without deposit)
  if (step === STEPS.length || bookingResult) {
    const r = bookingResult;
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4" data-testid="booking-confirmation">
        <Card className="max-w-md w-full bg-[#12121a] border-[#1e1e2e]">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-emerald-400" />
              </div>
            </div>
            <CardTitle className="text-xl text-zinc-100">Booking Confirmed!</CardTitle>
            <CardDescription>Your appointment has been scheduled</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-zinc-800/50 p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Service</span>
                <span className="text-zinc-100">{r?.service_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Barber</span>
                <span className="text-zinc-100">{r?.barber_name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Date & Time</span>
                <span className="text-zinc-100">
                  {r?.scheduled_at && new Date(r.scheduled_at).toLocaleString([], {
                    weekday: "short", month: "short", day: "numeric",
                    hour: "numeric", minute: "2-digit"
                  })}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-400">Price</span>
                <span className="text-zinc-100">${r?.price?.toFixed(2)}</span>
              </div>
            </div>
            {shop && (
              <div className="text-center text-sm text-zinc-500 space-y-1">
                <p className="flex items-center justify-center gap-1"><MapPin className="w-3 h-3" /> {shop.address}</p>
                <p className="flex items-center justify-center gap-1"><Phone className="w-3 h-3" /> {shop.phone}</p>
              </div>
            )}
            <Button className="w-full mt-4" variant="outline" onClick={() => { setBookingResult(null); setStep(0); setSelected(s => ({ ...s, slot: null, date: "" })); }} data-testid="book-another-btn">
              Book Another Appointment
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f]" data-testid="booking-page">
      {/* Header */}
      <div className="border-b border-[#1e1e2e] bg-[#12121a]">
        <div className="max-w-2xl mx-auto px-4 py-5 text-center">
          <div className="flex justify-center mb-2">
            <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
              <Scissors className="w-5 h-5 text-amber-400" />
            </div>
          </div>
          <h1 className="text-xl font-bold text-zinc-100" data-testid="shop-name">{shop?.name || "Book an Appointment"}</h1>
          {shop?.address && <p className="text-sm text-zinc-500 mt-1">{shop.address}</p>}
        </div>
      </div>

      {/* Progress */}
      <div className="max-w-2xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between mb-6">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                i < step ? "bg-amber-500 text-black" :
                i === step ? "bg-amber-500/20 text-amber-400 ring-2 ring-amber-500/40" :
                "bg-zinc-800 text-zinc-500"
              }`}>
                {i < step ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={`w-8 sm:w-12 h-0.5 mx-1 ${i < step ? "bg-amber-500" : "bg-zinc-800"}`} />
              )}
            </div>
          ))}
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2" data-testid="booking-error">
            <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}

        {/* Step 1: Service */}
        {step === 0 && (
          <div className="space-y-3" data-testid="step-service">
            <h2 className="text-lg font-semibold text-zinc-100 mb-1">Choose a Service</h2>
            <div className="grid gap-3">
              {services.map((svc) => (
                <button
                  key={svc.id}
                  onClick={() => { setSelected(s => ({ ...s, service: svc })); next(); }}
                  className={`w-full text-left rounded-lg border p-4 transition-all hover:border-amber-500/50 hover:bg-amber-500/5 ${
                    selected.service?.id === svc.id ? "border-amber-500 bg-amber-500/10" : "border-[#1e1e2e] bg-[#12121a]"
                  }`}
                  data-testid={`service-${svc.id}`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium text-zinc-100">{svc.name}</p>
                      <p className="text-sm text-zinc-500 mt-0.5">{svc.description}</p>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className="text-amber-400 font-semibold">${svc.price}</p>
                      <p className="text-xs text-zinc-500">{svc.duration_minutes} min</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Barber */}
        {step === 1 && (
          <div className="space-y-3" data-testid="step-barber">
            <h2 className="text-lg font-semibold text-zinc-100 mb-1">Choose a Barber</h2>
            <button
              onClick={() => { setSelected(s => ({ ...s, barber: null })); next(); }}
              className={`w-full text-left rounded-lg border p-4 transition-all hover:border-amber-500/50 hover:bg-amber-500/5 ${
                selected.barber === null ? "border-amber-500 bg-amber-500/10" : "border-[#1e1e2e] bg-[#12121a]"
              }`}
              data-testid="barber-any"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-zinc-700 flex items-center justify-center">
                  <User className="w-5 h-5 text-zinc-300" />
                </div>
                <div>
                  <p className="font-medium text-zinc-100">Any Available Barber</p>
                  <p className="text-sm text-zinc-500">First available</p>
                </div>
              </div>
            </button>
            {barbers.map((b) => (
              <button
                key={b.id}
                onClick={() => { setSelected(s => ({ ...s, barber: b })); next(); }}
                className={`w-full text-left rounded-lg border p-4 transition-all hover:border-amber-500/50 hover:bg-amber-500/5 ${
                  selected.barber?.id === b.id ? "border-amber-500 bg-amber-500/10" : "border-[#1e1e2e] bg-[#12121a]"
                }`}
                data-testid={`barber-${b.id}`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                    <span className="text-amber-400 font-semibold text-sm">{b.name.charAt(0)}</span>
                  </div>
                  <p className="font-medium text-zinc-100">{b.name}</p>
                </div>
              </button>
            ))}
            <div className="pt-2">
              <Button variant="ghost" size="sm" onClick={back} className="text-zinc-400" data-testid="back-btn-barber">
                <ChevronLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Date & Time */}
        {step === 2 && (
          <div className="space-y-4" data-testid="step-datetime">
            <h2 className="text-lg font-semibold text-zinc-100 mb-1">Pick a Date & Time</h2>

            {/* Date picker */}
            <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
              {dates.map((d) => (
                <button
                  key={d}
                  onClick={() => { setSelected(s => ({ ...s, date: d, slot: null })); }}
                  className={`shrink-0 rounded-lg border px-3 py-2 text-center transition-all ${
                    selected.date === d ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-[#1e1e2e] bg-[#12121a] text-zinc-400 hover:border-zinc-600"
                  }`}
                  data-testid={`date-${d}`}
                >
                  <p className="text-xs">{formatDate(d).split(",")[0]}</p>
                  <p className="font-semibold text-sm">{new Date(d + "T12:00:00").getDate()}</p>
                </button>
              ))}
            </div>

            {/* Time slots */}
            {selected.date && (
              <div>
                {slotsLoading ? (
                  <div className="text-center text-zinc-500 py-6">Loading available times...</div>
                ) : slots.length === 0 ? (
                  <div className="text-center text-zinc-500 py-6">No available slots for this date</div>
                ) : (
                  Object.entries(slotsByBarber).map(([barberName, barberSlots]) => (
                    <div key={barberName} className="mb-4">
                      <p className="text-sm text-zinc-400 mb-2 font-medium">{barberName}</p>
                      <div className="flex flex-wrap gap-2">
                        {barberSlots.map((s) => (
                          <button
                            key={`${s.barber_id}-${s.start}`}
                            onClick={() => setSelected(prev => ({ ...prev, slot: s }))}
                            className={`px-3 py-1.5 rounded-md text-sm border transition-all ${
                              selected.slot?.start === s.start && selected.slot?.barber_id === s.barber_id
                                ? "border-amber-500 bg-amber-500/10 text-amber-400"
                                : "border-[#1e1e2e] bg-[#12121a] text-zinc-300 hover:border-zinc-600"
                            }`}
                            data-testid={`slot-${s.start}`}
                          >
                            {formatSlotTime(s.start)}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            <div className="flex justify-between pt-2">
              <Button variant="ghost" size="sm" onClick={back} className="text-zinc-400" data-testid="back-btn-datetime">
                <ChevronLeft className="w-4 h-4 mr-1" /> Back
              </Button>
              <Button size="sm" onClick={next} disabled={!selected.slot} className="bg-amber-500 text-black hover:bg-amber-400" data-testid="next-btn-datetime">
                Next <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* Step 4: Client Info */}
        {step === 3 && (
          <div className="space-y-4" data-testid="step-info">
            <h2 className="text-lg font-semibold text-zinc-100 mb-1">Your Information</h2>
            <div className="space-y-3">
              <div>
                <Label className="text-zinc-300">Full Name *</Label>
                <Input
                  value={selected.name}
                  onChange={(e) => setSelected(s => ({ ...s, name: e.target.value }))}
                  placeholder="John Smith"
                  className="mt-1 bg-[#12121a] border-[#1e1e2e]"
                  data-testid="input-name"
                />
              </div>
              <div>
                <Label className="text-zinc-300">Phone Number *</Label>
                <Input
                  value={selected.phone}
                  onChange={(e) => setSelected(s => ({ ...s, phone: e.target.value }))}
                  placeholder="+1 (555) 000-0000"
                  className="mt-1 bg-[#12121a] border-[#1e1e2e]"
                  data-testid="input-phone"
                />
              </div>
              <div>
                <Label className="text-zinc-300">Email (optional)</Label>
                <Input
                  value={selected.email}
                  onChange={(e) => setSelected(s => ({ ...s, email: e.target.value }))}
                  placeholder="john@example.com"
                  className="mt-1 bg-[#12121a] border-[#1e1e2e]"
                  data-testid="input-email"
                />
              </div>
              <div>
                <Label className="text-zinc-300">Notes (optional)</Label>
                <Input
                  value={selected.notes}
                  onChange={(e) => setSelected(s => ({ ...s, notes: e.target.value }))}
                  placeholder="Any preferences..."
                  className="mt-1 bg-[#12121a] border-[#1e1e2e]"
                  data-testid="input-notes"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.sms_consent}
                  onChange={(e) => setSelected(s => ({ ...s, sms_consent: e.target.checked }))}
                  className="accent-amber-500"
                  data-testid="checkbox-sms"
                />
                Send me appointment reminders via SMS
              </label>
            </div>
            <div className="flex justify-between pt-2">
              <Button variant="ghost" size="sm" onClick={back} className="text-zinc-400" data-testid="back-btn-info">
                <ChevronLeft className="w-4 h-4 mr-1" /> Back
              </Button>
              <Button
                size="sm"
                onClick={next}
                disabled={!selected.name.trim() || !selected.phone.trim()}
                className="bg-amber-500 text-black hover:bg-amber-400"
                data-testid="next-btn-info"
              >
                Review Booking <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* Step 5: Confirm */}
        {step === 4 && (
          <div className="space-y-4" data-testid="step-confirm">
            <h2 className="text-lg font-semibold text-zinc-100 mb-1">Review & Confirm</h2>
            <Card className="bg-[#12121a] border-[#1e1e2e]">
              <CardContent className="p-4 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400 flex items-center gap-1"><Scissors className="w-3 h-3" /> Service</span>
                  <span className="text-zinc-100">{selected.service?.name}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400 flex items-center gap-1"><User className="w-3 h-3" /> Barber</span>
                  <span className="text-zinc-100">{selected.barber?.name || selected.slot?.barber_name || "Any Available"}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400 flex items-center gap-1"><Calendar className="w-3 h-3" /> Date</span>
                  <span className="text-zinc-100">
                    {selected.slot && new Date(selected.slot.start).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-400 flex items-center gap-1"><Clock className="w-3 h-3" /> Time</span>
                  <span className="text-zinc-100">{selected.slot && formatSlotTime(selected.slot.start)}</span>
                </div>
                <div className="border-t border-[#1e1e2e] pt-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-400">Name</span>
                    <span className="text-zinc-100">{selected.name}</span>
                  </div>
                  <div className="flex justify-between text-sm mt-1">
                    <span className="text-zinc-400">Phone</span>
                    <span className="text-zinc-100">{selected.phone}</span>
                  </div>
                </div>
                <div className="border-t border-[#1e1e2e] pt-2 flex justify-between">
                  <span className="text-zinc-300 font-medium">Total</span>
                  <span className="text-amber-400 font-bold text-lg">${selected.service?.price?.toFixed(2)}</span>
                </div>
              </CardContent>
            </Card>

            <p className="text-xs text-zinc-500 text-center">
              A deposit may be required depending on your booking time and history. You'll be redirected to pay securely via Stripe if needed.
            </p>

            <div className="flex justify-between pt-2">
              <Button variant="ghost" size="sm" onClick={back} className="text-zinc-400" data-testid="back-btn-confirm">
                <ChevronLeft className="w-4 h-4 mr-1" /> Back
              </Button>
              <Button
                onClick={handleBook}
                disabled={booking}
                className="bg-amber-500 text-black hover:bg-amber-400 gap-2"
                data-testid="confirm-booking-btn"
              >
                {booking ? "Booking..." : (
                  <><CreditCard className="w-4 h-4" /> Confirm Booking</>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
