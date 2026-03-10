"use client";

import { useState, useEffect } from "react";
import { Search, Clock, Layers, PoundSterling, Linkedin, Download } from "lucide-react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Lead, fetchLiveLeads } from "@/lib/api";

const TIER_COLORS: Record<string, string> = {
  HOT: "border-hot bg-hot text-white",
  WARM: "border-warm bg-warm text-white",
  COLD: "border-cold bg-cold text-white",
};

const BORDER_COLORS: Record<string, string> = {
  HOT: "border-l-hot",
  WARM: "border-l-warm",
  COLD: "border-l-cold",
};

const getSignalBadge = (key: string, val: number) => {
  if (val === 2) return <Badge variant="outline" className="font-mono text-xs px-2 bg-green/10 text-green border-green/30">{key.toUpperCase()}: 2/2</Badge>;
  if (val === 1) return <Badge variant="outline" className="font-mono text-xs px-2 bg-warm/10 text-warm border-warm/30">{key.toUpperCase()}: 1/2</Badge>;
  return <Badge variant="outline" className="font-mono text-xs px-2 bg-muted text-muted-foreground border-border">{key.toUpperCase()}: 0/2</Badge>;
};

export default function LeadsPage() {
  const [filter, setFilter] = useState("All");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLiveLeads().then((data) => {
      setLeads(data);
      setLoading(false);
    });
  }, []);

  const displayLeads = leads.filter(l => filter === "All" || l.tier === filter);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      
      {/* Top filter bar */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-surface p-4 rounded-lg border border-border/50">
        <div className="flex items-center gap-4 w-full md:w-auto flex-1">
          <div className="relative w-full max-w-[300px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Search brands..." 
              className="pl-9 bg-surface-2 border-border focus-visible:ring-primary w-full"
            />
          </div>
          
          <div className="flex bg-surface-2 rounded-md p-1 border border-border/50">
            {["All", "HOT", "WARM", "COLD"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                  filter === f 
                    ? "bg-primary text-white shadow-sm" 
                    : "text-muted-foreground hover:text-white"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <Select defaultValue="score">
            <SelectTrigger className="w-[180px] bg-surface-2 border-border">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent className="bg-surface border-border">
              <SelectItem value="score">Score &darr;</SelectItem>
              <SelectItem value="newest">Newest</SelectItem>
              <SelectItem value="days">Days Running</SelectItem>
            </SelectContent>
          </Select>
          
          <Button variant="outline" className="border-primary text-primary hover:bg-primary/10">
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Loading state mapping */}
      {loading && (
        <div className="w-full text-center py-20 text-muted-foreground font-mono animate-pulse">
          Fetching live records from Airtable...
        </div>
      )}
      
      {!loading && displayLeads.length === 0 && (
        <div className="w-full text-center py-20 text-muted-foreground font-mono">
          No leads found matching the current filter.
        </div>
      )}

      {/* Leads Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {displayLeads.map((lead) => (
          <Card key={lead.id} className={`bg-surface border-border/50 hover:bg-surface-2 transition-all hover:-translate-y-1 border-l-4 ${BORDER_COLORS[lead.tier]}`}>
            <CardContent className="p-6">
              
              {/* Header */}
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-display font-bold text-lg text-white leading-tight">{lead.brand}</h3>
                  <a href={lead.website} target="_blank" rel="noreferrer" className="text-xs text-muted-foreground hover:text-primary transition-colors">
                    {lead.website || "No website"}
                  </a>
                </div>
                <div className="flex flex-col items-end">
                  <Badge className={`px-2 py-1 ${TIER_COLORS[lead.tier]}`}>
                    {lead.tier}
                  </Badge>
                  <div className="mt-1 font-mono">
                    <span className="text-lg font-bold text-white">{lead.score}</span>
                    <span className="text-muted-foreground text-sm">/10</span>
                  </div>
                </div>
              </div>

              {/* Signals */}
              <div className="flex flex-wrap gap-2 mb-6">
                {getSignalBadge('s1', lead.signals?.s1 || 0)}
                {getSignalBadge('s2', lead.signals?.s2 || 0)}
                {getSignalBadge('s3', lead.signals?.s3 || 0)}
                {getSignalBadge('s4', lead.signals?.s4 || 0)}
                {getSignalBadge('s5', lead.signals?.s5 || 0)}
              </div>

              {/* Ad Intel Details */}
              <div className="grid grid-cols-3 gap-4 mb-6 p-4 rounded-lg bg-background border border-border/50">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-surface-2 flex items-center justify-center">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground">Days Running</span>
                    <span className="text-sm font-medium text-white">{lead.daysRunning} days</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-surface-2 flex items-center justify-center">
                    <Layers className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground">Active Ads</span>
                    <span className="text-sm font-medium text-white">{lead.numAds} ads</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-surface-2 flex items-center justify-center">
                    <PoundSterling className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground">Est. Ad Spend</span>
                    <span className="text-sm font-medium text-white">{lead.estSpend}</span>
                  </div>
                </div>
              </div>

              {/* Ad Copy preview */}
              <div className="mb-6">
                <p className="text-xs text-muted-foreground mb-1 font-medium">Top Ad Copy / Email Preview</p>
                <div className="bg-surface-2 p-3 rounded border border-border/50 relative overflow-hidden group max-h-[100px]">
                  <p className="font-mono text-xs text-muted-foreground line-clamp-3 leading-relaxed whitespace-pre-wrap">
                    {lead.adCopy}
                  </p>
                  <div className="absolute inset-x-0 bottom-0 h-full bg-gradient-to-t from-surface-2 via-surface-2/80 to-transparent flex items-end justify-center pb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button className="text-[10px] text-primary hover:text-white font-medium">View full copy</button>
                  </div>
                </div>
              </div>

              {/* Contact section */}
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-background/50">
                <div className="flex items-center gap-3">
                  <Avatar className="h-10 w-10 border border-border">
                    <AvatarFallback className="bg-primary/20 text-primary font-bold text-xs uppercase">
                      {lead.contact?.name ? lead.contact.name.substring(0, 2) : "??"}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-white leading-none">{lead.contact?.name || "Unknown"}</span>
                    <span className="text-xs text-muted-foreground mt-1 truncate max-w-[200px]">{lead.contact?.email || lead.contact?.title}</span>
                  </div>
                </div>
                
                <div className="flex items-center gap-4">
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] text-muted-foreground mb-0.5">Email Status</span>
                    {lead.contact?.confirmed ? (
                      <span className="inline-flex flex-row items-center font-medium text-xs text-green">✓ Found</span>
                    ) : (
                      <span className="inline-flex flex-row items-center text-xs text-muted-foreground">Not found</span>
                    )}
                  </div>
                  <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-[#0A66C2]/10 hover:text-[#0A66C2]">
                    <Linkedin className="h-4 w-4" />
                  </Button>
                </div>
              </div>

            </CardContent>
            
            {/* Footer row */}
            <CardFooter className="bg-surface-2/30 border-t border-border/50 p-4 flex justify-between items-center rounded-b-lg">
              <span className="text-xs text-muted-foreground">
                Added {new Date(lead.dateAdded).toLocaleDateString("en-GB", { day: '2-digit', month: 'short', year: 'numeric' })}
              </span>
              <div className="flex gap-2">
                <Button variant="ghost" className="text-sm font-medium hover:bg-surface hover:text-white h-9">
                  View Emails
                </Button>
                {lead.pushedToInstantly ? (
                  <Button className="h-9 bg-green/10 text-green hover:bg-green/20 border border-green/20" variant="outline">
                    Pushed ✓
                  </Button>
                ) : (
                  <Button className="h-9 bg-primary hover:bg-primary/90 text-white shadow-[0_0_15px_rgba(124,58,237,0.3)]">
                    Push to Instantly
                  </Button>
                )}
              </div>
            </CardFooter>
          </Card>
        ))}
      </div>
      
    </div>
  );
}
