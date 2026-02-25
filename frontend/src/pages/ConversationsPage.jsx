import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { ScrollArea } from "../components/ui/scroll-area";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { 
  MessageSquare, 
  Search, 
  User,
  Phone,
  Wifi,
  WifiOff,
  RefreshCw,
  Zap
} from "lucide-react";
import { format } from "date-fns";

export default function ConversationsPage() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [selectedClient, setSelectedClient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const messagesEndRef = useRef(null);
  
  // Real-time polling state
  const [liveMode, setLiveMode] = useState(true);
  const [lastPollTime, setLastPollTime] = useState(null);
  const [newMessageCount, setNewMessageCount] = useState(0);
  const pollIntervalRef = useRef(null);

  // Initial fetch
  useEffect(() => {
    fetchConversations();
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Fetch messages when client selected
  useEffect(() => {
    if (clientId) {
      fetchMessages(clientId);
      setNewMessageCount(0);
    }
  }, [clientId]);

  // Set up polling
  useEffect(() => {
    if (liveMode) {
      // Start polling
      pollIntervalRef.current = setInterval(() => {
        pollForNewMessages();
      }, 3000);
      
      return () => {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
        }
      };
    } else {
      // Stop polling
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    }
  }, [liveMode, clientId, lastPollTime]);

  // Auto-scroll on new messages
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchConversations = async () => {
    try {
      const response = await axios.get(`${API}/conversations`);
      setConversations(response.data.conversations);
    } catch (error) {
      console.error("Failed to fetch conversations:", error);
      toast.error("Failed to load conversations");
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (cId) => {
    try {
      const response = await axios.get(`${API}/conversations/${cId}`);
      setMessages(response.data.messages);
      setSelectedClient(response.data.client);
      
      // Set initial poll time to latest message
      if (response.data.messages.length > 0) {
        const latest = response.data.messages[response.data.messages.length - 1];
        setLastPollTime(latest.created_at);
      }
    } catch (error) {
      console.error("Failed to fetch messages:", error);
      toast.error("Failed to load messages");
    }
  };

  const pollForNewMessages = useCallback(async () => {
    if (!liveMode) return;
    
    try {
      const params = new URLSearchParams();
      if (lastPollTime) params.append("since", lastPollTime);
      if (clientId) params.append("client_id", clientId);
      
      const response = await axios.get(`${API}/conversations/poll/new?${params}`);
      
      if (response.data.messages.length > 0) {
        if (clientId) {
          // Add new messages to current conversation
          setMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id));
            const newMsgs = response.data.messages.filter(m => !existingIds.has(m.id));
            return [...prev, ...newMsgs];
          });
        } else {
          // Update new message count indicator
          setNewMessageCount(prev => prev + response.data.messages.length);
        }
        
        // Update poll time
        if (response.data.latest_timestamp) {
          setLastPollTime(response.data.latest_timestamp);
        }
        
        // Refresh conversation list
        fetchConversations();
      }
    } catch (error) {
      console.error("Polling error:", error);
    }
  }, [liveMode, lastPollTime, clientId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSelectConversation = (cId) => {
    navigate(`/conversations/${cId}`);
    setNewMessageCount(0);
  };

  const formatMessageTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return format(date, "h:mm a");
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return format(date, "EEEE");
    } else {
      return format(date, "MMM d");
    }
  };

  const filteredConversations = useMemo(() =>
    conversations.filter(conv =>
      conv.client_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      conv.client_phone?.includes(searchTerm)
    ),
    [conversations, searchTerm]
  );

  return (
    <Layout title="Conversations">
      <div data-testid="conversations-page" className="space-y-4">
        {/* Live Mode Toggle */}
        <Card className="bg-card border-border">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  {liveMode ? (
                    <Wifi className="w-5 h-5 text-emerald-400 animate-pulse" />
                  ) : (
                    <WifiOff className="w-5 h-5 text-muted-foreground" />
                  )}
                  <Label htmlFor="live-mode" className="font-medium">
                    Live Updates
                  </Label>
                </div>
                <Switch
                  id="live-mode"
                  data-testid="live-mode-toggle"
                  checked={liveMode}
                  onCheckedChange={setLiveMode}
                />
                {liveMode && (
                  <span className="text-xs text-muted-foreground">
                    Auto-refreshing every 3s
                  </span>
                )}
              </div>
              
              {newMessageCount > 0 && !clientId && (
                <Badge className="bg-primary text-primary-foreground animate-pulse">
                  <Zap className="w-3 h-3 mr-1" />
                  {newMessageCount} new message{newMessageCount > 1 ? "s" : ""}
                </Badge>
              )}
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  fetchConversations();
                  if (clientId) fetchMessages(clientId);
                }}
                data-testid="refresh-conversations"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-280px)]">
          {/* Conversation List */}
          <Card className="bg-card border-border lg:col-span-1 flex flex-col">
            <CardHeader className="border-b border-border pb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  data-testid="conversation-search"
                  placeholder="Search conversations..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 bg-input/50 border-input"
                />
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-1 overflow-hidden">
              <ScrollArea className="h-full">
                {loading ? (
                  <div className="p-4 space-y-4">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="animate-pulse flex items-center gap-3 p-3">
                        <div className="w-10 h-10 bg-muted rounded-full" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 bg-muted rounded w-24" />
                          <div className="h-3 bg-muted rounded w-36" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : filteredConversations.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No conversations found</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {filteredConversations.map((conv) => (
                      <button
                        key={conv.client_id}
                        data-testid={`conversation-item-${conv.client_id}`}
                        onClick={() => handleSelectConversation(conv.client_id)}
                        className={`w-full p-4 text-left hover:bg-accent/50 transition-colors ${
                          clientId === conv.client_id ? 'bg-primary/10 border-l-2 border-primary' : ''
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-secondary rounded-full flex items-center justify-center relative">
                            <User className="w-5 h-5 text-muted-foreground" />
                            {conv.last_direction === "inbound" && (
                              <div className="absolute -top-1 -right-1 w-3 h-3 bg-primary rounded-full" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <p className="font-medium truncate">
                                {conv.client_name || "Unknown"}
                              </p>
                              <span className="text-xs text-muted-foreground">
                                {formatMessageTime(conv.last_at)}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground truncate">
                              {conv.last_direction === "outbound" && (
                                <span className="text-primary">You: </span>
                              )}
                              {conv.last_message}
                            </p>
                          </div>
                          {conv.total_messages > 0 && (
                            <Badge variant="secondary" className="text-xs shrink-0">
                              {conv.total_messages}
                            </Badge>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Message Thread */}
          <Card className="bg-card border-border lg:col-span-2 flex flex-col">
            {clientId && selectedClient ? (
              <>
                {/* Chat Header */}
                <CardHeader className="border-b border-border pb-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-secondary rounded-full flex items-center justify-center">
                        <User className="w-5 h-5 text-muted-foreground" />
                      </div>
                      <div>
                        <h3 className="font-medium">{selectedClient.name}</h3>
                        <p className="text-sm text-muted-foreground flex items-center gap-1">
                          <Phone className="w-3 h-3" />
                          {selectedClient.phone}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {liveMode && (
                        <Badge variant="outline" className="text-emerald-400 border-emerald-400/50">
                          <Wifi className="w-3 h-3 mr-1" />
                          Live
                        </Badge>
                      )}
                      <Badge 
                        className={selectedClient.sms_consent ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}
                      >
                        {selectedClient.sms_consent ? "SMS Consent" : "No Consent"}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>

                {/* Messages */}
                <CardContent className="flex-1 p-4 overflow-hidden">
                  <ScrollArea className="h-full pr-4">
                    <div className="space-y-4">
                      {messages.map((msg, index) => (
                        <div
                          key={msg.id || index}
                          data-testid={`message-${msg.direction}`}
                          className={`flex ${msg.direction === "outbound" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-2 duration-300`}
                        >
                          <div
                            className={`max-w-[80%] px-4 py-3 ${
                              msg.direction === "outbound"
                                ? "bg-primary text-primary-foreground rounded-2xl rounded-br-sm"
                                : "bg-secondary text-foreground rounded-2xl rounded-bl-sm"
                            }`}
                          >
                            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                            <p className={`text-xs mt-1 ${
                              msg.direction === "outbound" ? "text-primary-foreground/70" : "text-muted-foreground"
                            }`}>
                              {format(new Date(msg.created_at), "h:mm a")}
                            </p>
                          </div>
                        </div>
                      ))}
                      <div ref={messagesEndRef} />
                    </div>
                  </ScrollArea>
                </CardContent>

                {/* Footer */}
                <div className="p-4 border-t border-border">
                  <p className="text-xs text-muted-foreground text-center">
                    Messages are handled automatically by the Autopilot. 
                    {liveMode && " New messages will appear in real-time."}
                  </p>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <MessageSquare className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">Select a conversation</p>
                  <p className="text-sm">Choose from the list to view messages</p>
                  {liveMode && (
                    <Badge variant="outline" className="mt-4 text-emerald-400 border-emerald-400/50">
                      <Wifi className="w-3 h-3 mr-1" />
                      Live mode active - watching for new messages
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </Layout>
  );
}
