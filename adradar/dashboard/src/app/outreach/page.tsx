"use client";

import { useState, useEffect } from "react";
import { Mail, Copy, Edit2, Play, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Lead, fetchLiveLeads } from "@/lib/api";

export default function OutreachPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);

  useEffect(() => {
    fetchLiveLeads().then((data) => {
      // Filter for HOT leads that have an email generated
      const hotLeads = data.filter(l => l.score >= 8);
      setLeads(hotLeads);
      if (hotLeads.length > 0) {
        setSelectedLeadId(hotLeads[0].id);
      }
      setLoading(false);
    });
  }, []);

  const selectedLead = leads.find(l => l.id === selectedLeadId);

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-8rem)] animate-in fade-in duration-500">
      
      {/* Left Panel: Lead List */}
      <div className="w-full lg:w-[35%] flex flex-col gap-4">
        <h2 className="font-display font-medium text-lg px-1 flex items-center text-white">
          <Mail className="w-5 h-5 mr-2 text-primary" />
          Pending Sequences
        </h2>
        
        <ScrollArea className="flex-1 rounded-lg border border-border/50 bg-surface/50 p-2">
          {loading && (
            <div className="p-8 text-center text-muted-foreground animate-pulse text-sm font-mono">
              Loading AI outreach sequences...
            </div>
          )}
          {!loading && leads.length === 0 && (
             <div className="p-8 text-center text-muted-foreground text-sm font-mono">
              No HOT leads available for outreach.
            </div>
          )}

          {leads.map((lead) => (
            <div 
              key={lead.id}
              onClick={() => setSelectedLeadId(lead.id)}
              className={`p-4 rounded-md cursor-pointer transition-all mb-2 flex flex-col gap-2 ${
                selectedLeadId === lead.id 
                  ? "bg-surface-2 border-l-4 border-l-primary shadow-sm"
                  : "hover:bg-surface-2 border-l-4 border-l-transparent text-muted-foreground"
              }`}
            >
              <div className="flex justify-between items-center">
                <span className={`font-medium ${selectedLeadId === lead.id ? 'text-white' : ''}`}>
                  {lead.brand}
                </span>
                <Badge className={
                  lead.score >= 9 ? "bg-hot text-white" : 
                  lead.score >= 8 ? "bg-warm text-white" : "bg-cold text-white"
                }>
                  Score: {lead.score}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs">Generated Email Ready</span>
                {lead.pushedToInstantly && (
                  <CheckCircle2 className="w-4 h-4 text-green" />
                )}
              </div>
            </div>
          ))}
        </ScrollArea>
      </div>

      {/* Right Panel: Email Viewer */}
      <div className="w-full lg:w-[65%] flex flex-col gap-4">
        {selectedLead ? (
          <>
            <div className="flex justify-between items-center px-1">
              <div>
                <h2 className="font-display font-bold text-xl text-white">Sequence: {selectedLead.brand}</h2>
                <p className="text-sm text-muted-foreground">Generated today • Targeted at {selectedLead.contact?.name || "Founder"}</p>
              </div>
            </div>
            
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-6 pb-6">
                <Card className="bg-surface border-border/50 hover:border-primary/30 transition-colors">
                  <CardHeader className="bg-surface-2/30 border-b border-border/50 py-3">
                    <div className="flex justify-between items-center">
                      <CardTitle className="text-sm font-medium text-white flex items-center">
                        <span className="bg-primary/20 text-primary w-6 h-6 rounded flex items-center justify-center text-xs mr-2">E1</span>
                        Day 1 — Cold Email Output (from Airtable)
                      </CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="p-5 pt-4">
                    <div className="mb-4">
                      <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Subject</span>
                      <p className="font-medium text-white mt-1">Quick question regarding {selectedLead.brand}</p>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Body</span>
                      <div className="mt-2 text-sm text-foreground whitespace-pre-wrap leading-relaxed bg-background/50 p-4 rounded-md border border-border/40 font-sans">
                        {selectedLead.adCopy || "No AI email generated yet in the Airtable record."}
                      </div>
                    </div>
                    
                    {/* Footer Actions */}
                    <div className="flex justify-between items-center mt-4 pt-4 border-t border-border/30">
                      <span className="text-xs text-muted-foreground">AI Generated</span>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground hover:text-white">
                          <Edit2 className="w-3 h-3 mr-2" /> Edit
                        </Button>
                        <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground hover:text-white">
                          <Copy className="w-3 h-3 mr-2" /> Copy
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </ScrollArea>

            {/* Sticky bottom CTA */}
            <div className="bg-surface p-4 rounded-lg border border-border/50 flex justify-between items-center shadow-lg transform -translate-y-2">
              <div className="flex flex-col">
                <span className="font-medium text-white">Instantly.ai Integration</span>
                <span className="text-xs text-muted-foreground">Ready to push 1 email</span>
              </div>
              
              {selectedLead.pushedToInstantly ? (
                <div className="flex items-center px-4 py-2 bg-green/10 text-green rounded-md border border-green/20 font-medium tracking-wide text-sm">
                  <CheckCircle2 className="w-5 h-5 mr-2" />
                  Pushed to Campaign
                </div>
              ) : (
                <Button className="bg-primary hover:bg-primary/90 text-white shadow-[0_0_15px_rgba(124,58,237,0.3)] min-w-[150px]">
                  <Play className="w-4 h-4 mr-2" fill="currentColor" />
                  Push Sequence
                </Button>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground bg-surface/30 rounded-lg border border-border/50 border-dashed">
            <Mail className="h-12 w-12 mb-4 opacity-20" />
            <p>Select a HOT lead from the queue to review AI outreach copy.</p>
          </div>
        )}
      </div>

    </div>
  );
}
