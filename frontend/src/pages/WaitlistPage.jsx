import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../components/ui/alert-dialog";
import { toast } from "sonner";
import { 
  Users, 
  Clock,
  Calendar,
  Scissors,
  Phone,
  Trash2,
  User
} from "lucide-react";
import { format } from "date-fns";

export default function WaitlistPage() {
  const [waitlist, setWaitlist] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWaitlist();
  }, []);

  const fetchWaitlist = async () => {
    try {
      const response = await axios.get(`${API}/waitlist`);
      setWaitlist(response.data.waitlist);
    } catch (error) {
      console.error("Failed to fetch waitlist:", error);
      toast.error("Failed to load waitlist");
    } finally {
      setLoading(false);
    }
  };

  const removeFromWaitlist = async (entryId) => {
    try {
      await axios.delete(`${API}/waitlist/${entryId}`);
      toast.success("Removed from waitlist");
      fetchWaitlist();
    } catch (error) {
      toast.error("Failed to remove from waitlist");
    }
  };

  return (
    <Layout title="Waitlist">
      <div data-testid="waitlist-page" className="space-y-6">
        {/* Summary Card */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Users className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h3 className="font-heading text-xl font-semibold">Active Waitlist</h3>
                  <p className="text-muted-foreground">
                    {waitlist.length} {waitlist.length === 1 ? "client" : "clients"} waiting for slots
                  </p>
                </div>
              </div>
              <Badge variant="secondary" className="text-lg px-4 py-2 font-mono">
                {waitlist.length}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Waitlist Table */}
        <Card className="bg-card border-border">
          <CardHeader className="border-b border-border">
            <CardTitle className="font-heading text-lg">Waitlist Entries</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">Client</TableHead>
                  <TableHead className="text-muted-foreground">Service</TableHead>
                  <TableHead className="text-muted-foreground">Preferred Date</TableHead>
                  <TableHead className="text-muted-foreground">Flexibility</TableHead>
                  <TableHead className="text-muted-foreground">Contact Attempts</TableHead>
                  <TableHead className="text-muted-foreground">Added</TableHead>
                  <TableHead className="text-muted-foreground">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(3)].map((_, i) => (
                    <TableRow key={i} className="border-border">
                      <TableCell colSpan={7}>
                        <div className="h-12 bg-muted/50 animate-pulse rounded" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : waitlist.length === 0 ? (
                  <TableRow className="border-border">
                    <TableCell colSpan={7} className="text-center py-12">
                      <div className="text-muted-foreground">
                        <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg">No one on the waitlist</p>
                        <p className="text-sm">Clients will appear here when slots are full</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  waitlist.map((entry) => (
                    <TableRow 
                      key={entry.id} 
                      className="border-border hover:bg-accent/30"
                      data-testid={`waitlist-row-${entry.id}`}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center">
                            <User className="w-4 h-4 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="font-medium">{entry.client?.name || "Unknown"}</p>
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Phone className="w-3 h-3" />
                              {entry.client?.phone}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Scissors className="w-4 h-4 text-muted-foreground" />
                          {entry.service?.name || "Unknown"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          {format(new Date(entry.preferred_date), "MMM d, yyyy")}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          ± {entry.flexible_hours} hours
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono">{entry.contact_attempts}</span>
                        {entry.last_contacted && (
                          <p className="text-xs text-muted-foreground">
                            Last: {format(new Date(entry.last_contacted), "MMM d")}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {format(new Date(entry.created_at), "MMM d, yyyy")}
                      </TableCell>
                      <TableCell>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-muted-foreground hover:text-destructive"
                              data-testid={`remove-waitlist-${entry.id}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Remove from Waitlist?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This will remove {entry.client?.name || "this client"} from the waitlist. 
                                They won't be notified when a slot opens up.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => removeFromWaitlist(entry.id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Remove
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Info Card */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center shrink-0">
                <Clock className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h4 className="font-medium mb-1">How Waitlist Filling Works</h4>
                <p className="text-sm text-muted-foreground">
                  When an appointment is cancelled, the system automatically contacts waitlist clients 
                  who match the cancelled time slot. Clients are contacted in order of when they joined 
                  the waitlist, with fewest contact attempts first.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
