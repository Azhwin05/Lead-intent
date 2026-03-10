"use client";

import { useEffect, useState } from "react";
import { Target, Flame, Send, Activity } from "lucide-react";
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Lead, fetchLiveLeads } from "@/lib/api";

const AREA_DATA = [
  { day: "Mon", hot: 4, warm: 6, cold: 12 },
  { day: "Tue", hot: 5, warm: 8, cold: 15 },
  { day: "Wed", hot: 7, warm: 5, cold: 10 },
  { day: "Thu", hot: 3, warm: 9, cold: 18 },
  { day: "Fri", hot: 8, warm: 7, cold: 14 },
  { day: "Sat", hot: 2, warm: 4, cold: 8 },
  { day: "Sun", hot: 9, warm: 8, cold: 11 },
];

const PIE_DATA = [
  { name: "Creative Fatigue", value: 14, color: "#ef4444" },
  { name: "Desperation Testing", value: 10, color: "#f59e0b" },
  { name: "Copy Quality", value: 9, color: "#7c3aed" },
  { name: "Paid Traffic Dep", value: 8, color: "#10b981" },
  { name: "Team Size Risk", value: 6, color: "#3b82f6" },
];

const getScoreColor = (score: number) => {
  if (score >= 9) return "bg-hot text-white";
  if (score >= 8) return "bg-warm text-white";
  return "bg-cold text-white";
};

const getSignalColor = (val: number) => {
  if (val === 2) return "bg-green/20 text-green border-green/30";
  if (val === 1) return "bg-warm/20 text-warm border-warm/30";
  return "bg-muted text-muted-foreground border-border";
};

export default function DashboardPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLiveLeads().then((data) => {
      setLeads(data);
      setLoading(false);
    });
  }, []);

  const hotLeads = leads.filter((l) => l.score >= 8);
  const pushedLeads = leads.filter((l) => l.pushedToInstantly);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-surface hover:bg-surface-2 transition-all hover:scale-[1.01] border-border/50">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Total Leads Extracted</p>
                <h3 className="text-3xl font-mono font-bold text-white">{leads.length}</h3>
              </div>
              <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center">
                <Target className="h-6 w-6 text-primary" />
              </div>
            </div>
            <p className="text-sm text-green mt-4">Loaded from Airtable</p>
          </CardContent>
        </Card>

        <Card className="bg-surface hover:bg-surface-2 transition-all hover:scale-[1.01] border-hot glow-red">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">HOT Leads</p>
                <h3 className="text-3xl font-mono font-bold text-white">{hotLeads.length}</h3>
              </div>
              <div className="h-12 w-12 bg-hot/10 rounded-full flex items-center justify-center">
                <Flame className="h-6 w-6 text-hot" />
              </div>
            </div>
            <p className="text-sm text-muted-foreground mt-4">Score 8-10 — Ready for Outreach</p>
          </CardContent>
        </Card>

        <Card className="bg-surface hover:bg-surface-2 transition-all hover:scale-[1.01] border-border/50">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Emails Pushed</p>
                <h3 className="text-3xl font-mono font-bold text-white">{pushedLeads.length}</h3>
              </div>
              <div className="h-12 w-12 bg-green/10 rounded-full flex items-center justify-center">
                <Send className="h-6 w-6 text-green" />
              </div>
            </div>
            <p className="text-sm text-muted-foreground mt-4">Sent to Instantly.ai</p>
          </CardContent>
        </Card>

        <Card className="bg-surface hover:bg-surface-2 transition-all hover:scale-[1.01] border-border/50">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Backend Connection</p>
                <h3 className="text-xl font-mono font-bold text-white uppercase">{loading ? "Loading..." : leads.length > 0 ? "Live" : "No Data"}</h3>
              </div>
              <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center relative">
                <Activity className="h-6 w-6 text-primary" />
                <span className={`absolute top-0 right-0 h-3 w-3 rounded-full ${loading ? "bg-warm" : "bg-green"} animate-pulse border-2 border-surface`} />
              </div>
            </div>
            <p className="text-sm text-muted-foreground mt-4">Python Pipeline Sync</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts ... Keep charts the same for now visually */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 bg-surface border-border/50">
          <CardHeader>
            <CardTitle className="font-display">Lead Quality Breakdown — Last 7 Days (Mock History)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={AREA_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorHot" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorWarm" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorCold" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" stroke="#475569" tick={{ fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#1e2d45', borderRadius: '8px' }}
                    itemStyle={{ color: '#f1f5f9' }}
                  />
                  <Area type="monotone" dataKey="hot" stackId="1" stroke="#ef4444" fill="url(#colorHot)" strokeWidth={2} />
                  <Area type="monotone" dataKey="warm" stackId="1" stroke="#f59e0b" fill="url(#colorWarm)" strokeWidth={2} />
                  <Area type="monotone" dataKey="cold" stackId="1" stroke="#3b82f6" fill="url(#colorCold)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-surface border-border/50">
          <CardHeader>
            <CardTitle className="font-display">Top Scoring Signals Today</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            <div className="h-[220px] w-full relative flex items-center justify-center mt-2">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={PIE_DATA}
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    stroke="none"
                  >
                    {PIE_DATA.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#1e2d45', borderRadius: '8px' }}
                    itemStyle={{ color: '#f1f5f9' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-2xl font-mono font-bold text-white">Live</span>
              </div>
            </div>
            <div className="w-full space-y-2 mt-6">
              {PIE_DATA.map((item) => (
                <div key={item.name} className="flex items-center justify-between text-sm">
                  <div className="flex items-center text-muted-foreground">
                    <span className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: item.color }} />
                    {item.name}
                  </div>
                  <span className="font-mono text-white">{item.value}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* LIVE Leads Table */}
      <Card className="bg-surface border-border/50 overflow-hidden">
        <CardHeader className="bg-surface-2/50 border-b border-border/50">
          <CardTitle className="font-display flex items-center text-lg text-white">
            <Flame className="w-5 h-5 text-hot mr-2" />
            🔥 Live HOT Leads from Airtable
          </CardTitle>
          <CardDescription>Leads scoring 8-10 dynamically loaded from backend</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-surface-2/30">
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className="text-muted-foreground font-medium w-[200px] pl-6">Brand</TableHead>
                <TableHead className="text-center text-muted-foreground font-medium">Score</TableHead>
                <TableHead className="text-center text-muted-foreground font-medium">Fatigue</TableHead>
                <TableHead className="text-center text-muted-foreground font-medium">Desperation</TableHead>
                <TableHead className="text-center text-muted-foreground font-medium">Copy Qual.</TableHead>
                <TableHead className="text-muted-foreground font-medium">Contact Details</TableHead>
                <TableHead className="text-muted-foreground font-medium">Status</TableHead>
                <TableHead className="text-right text-muted-foreground font-medium pr-6">Instantly Push</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    Fetching latest leads from backend...
                  </TableCell>
                </TableRow>
              )}
              {!loading && hotLeads.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                    No HOT leads currently in the Airtable database.
                  </TableCell>
                </TableRow>
              )}
              {hotLeads.map((lead) => (
                <TableRow key={lead.id} className="border-border/50 hover:bg-surface-2/50 transition-colors group">
                  <TableCell className="font-medium pl-6">
                    <div className="flex flex-col w-[180px] overflow-hidden text-ellipsis whitespace-nowrap">
                      <span className="text-white">{lead.brand}</span>
                      <a href={lead.website} target="_blank" rel="noreferrer" className="text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity hover:text-primary">
                        {lead.website || "No site"}
                      </a>
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge className={`font-mono px-2 py-0.5 ${getScoreColor(lead.score)} hover:${getScoreColor(lead.score)}`}>
                      {lead.score}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`px-1.5 py-0 rounded font-mono text-[10px] ${getSignalColor(lead.signals?.s1 || 0)}`}>
                      {lead.signals?.s1 || 0}/2
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`px-1.5 py-0 rounded font-mono text-[10px] ${getSignalColor(lead.signals?.s2 || 0)}`}>
                      {lead.signals?.s2 || 0}/2
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`px-1.5 py-0 rounded font-mono text-[10px] ${getSignalColor(lead.signals?.s3 || 0)}`}>
                      {lead.signals?.s3 || 0}/2
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="text-sm text-white">{lead.contact?.name || "Unknown"}</span>
                      <span className="text-xs text-muted-foreground truncate max-w-[150px]">{lead.contact?.email || lead.contact?.title}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {lead.contact?.confirmed ? (
                      <span className="inline-flex flex-row items-center text-xs font-medium text-green">
                        ✓ Found
                      </span>
                    ) : (
                      <span className="inline-flex flex-row items-center text-xs text-muted-foreground">
                        Not Enriched
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right pr-6">
                    {lead.pushedToInstantly ? (
                      <Badge className="bg-green/10 text-green hover:bg-green/20 border-green/20">
                        Pushed to Instantly
                      </Badge>
                    ) : (
                      <Badge className="bg-warm/10 text-warm hover:bg-warm/20 border-warm/20">
                        Pending
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
