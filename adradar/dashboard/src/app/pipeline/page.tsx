"use client";

import { useState, useEffect } from "react";
import { Activity, ArrowRight, CheckCircle2, Play, Database, BrainCircuit, MessageSquare } from "lucide-react";
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { triggerPipelineRun, fetchPipelineHistory, PipelineRun } from "@/lib/api";

const DAILY_LEADS = [
  { day: "24 Feb", hot: 5, warm: 10, cold: 15 },
  { day: "25 Feb", hot: 7, warm: 12, cold: 18 },
  { day: "26 Feb", hot: 4, warm: 9, cold: 11 },
  { day: "27 Feb", hot: 8, warm: 14, cold: 20 },
  { day: "28 Feb", hot: 6, warm: 11, cold: 16 },
  { day: "01 Mar", hot: 3, warm: 8, cold: 12 },
  { day: "02 Mar", hot: 9, warm: 15, cold: 22 },
  { day: "03 Mar", hot: 12, warm: 21, cold: 25 },
  { day: "04 Mar", hot: 4, warm: 10, cold: 12 },
  { day: "05 Mar", hot: 9, warm: 11, cold: 19 },
  { day: "06 Mar", hot: 6, warm: 14, cold: 18 },
  { day: "07 Mar", hot: 11, warm: 18, cold: 22 },
  { day: "08 Mar", hot: 5, warm: 9, cold: 15 },
  { day: "09 Mar", hot: 8, warm: 12, cold: 14 },
];

const SCORE_DISTRIBUTION = [
  { score: "1", count: 2, fill: "#3b82f6" },
  { score: "2", count: 5, fill: "#3b82f6" },
  { score: "3", count: 12, fill: "#3b82f6" },
  { score: "4", count: 18, fill: "#3b82f6" },
  { score: "5", count: 25, fill: "#f59e0b" },
  { score: "6", count: 32, fill: "#f59e0b" },
  { score: "7", count: 28, fill: "#f59e0b" },
  { score: "8", count: 15, fill: "#ef4444" },
  { score: "9", count: 8, fill: "#ef4444" },
  { score: "10", count: 3, fill: "#ef4444" },
];

const PIPELINE_STEPS = [
  { id: 1, name: "Scrape Meta", result: "147 found", done: true },
  { id: 2, name: "Filter", result: "89 passed", done: true },
  { id: 3, name: "Enrich Apollo", result: "76 enriched", done: true },
  { id: 4, name: "Enrich Traffic", result: "76 enriched", done: true },
  { id: 5, name: "Score", result: "34 scored", done: true },
  { id: 6, name: "Write Emails", result: "8 written", done: true },
  { id: 7, name: "Sheet Export", result: "Done", done: true },
  { id: 8, name: "Instantly Push", result: "8 pushed", done: true },
  { id: 9, name: "Slack Alert", result: "Sent", done: true },
];

export default function PipelinePage() {
  const [history, setHistory] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPipelineHistory()
      .then(data => {
        setHistory(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const handleRunPipeline = async () => {
    toast.loading("Triggering internal Python Pipeline...", { id: "pipeline_run" });
    const success = await triggerPipelineRun();
    
    if (success) {
      toast.success("Pipeline started! This sequence takes 3-5 minutes depending on volume.", { id: "pipeline_run", duration: 5000 });
      // Optimistically add a running row
      setHistory(prev => [{
        date: "Just Now",
        scraped: "-",
        filtered: "-",
        enriched: "-",
        hot: "-",
        warm: "-",
        cold: "-",
        pushed: "-",
        duration: "Running...",
        current: true
      }, ...prev]);
    } else {
      toast.error("Failed to trigger pipeline. Is Python backend running?", { id: "pipeline_run" });
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      
      {/* Header controls (New layout similar to the previous attempt) */}
      <div className="flex justify-between items-center bg-surface p-4 rounded-lg border border-border/50">
        <div>
          <h2 className="font-display font-medium text-lg text-white">System Logs & Metrics</h2>
          <p className="text-sm text-muted-foreground mt-1">Review historical pipeline execution stats</p>
        </div>
        <Button 
          onClick={handleRunPipeline}
          className="bg-primary hover:bg-primary/90 text-white shadow-[0_0_15px_rgba(124,58,237,0.3)] transition-all"
        >
          <Play className="w-4 h-4 mr-2" fill="currentColor" />
          Force Run Logic Now
        </Button>
      </div>

      {/* Run History Table */}
      <Card className="bg-surface border-border/50 overflow-hidden">
        <CardHeader className="bg-surface-2/50 border-b border-border/50">
          <CardTitle className="font-display flex items-center text-lg text-white">
            <Activity className="w-5 h-5 text-primary mr-2" />
            Backend Python Run History
          </CardTitle>
          <CardDescription>Live execution logs directly from FastAPI/Airtable</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-surface-2/30">
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className="text-muted-foreground font-medium pl-6">Date</TableHead>
                <TableHead className="text-right text-muted-foreground font-medium"><Database className="w-4 h-4 inline mr-1"/>Scraped</TableHead>
                <TableHead className="text-right text-muted-foreground font-medium">Filtered</TableHead>
                <TableHead className="text-right text-muted-foreground font-medium"><BrainCircuit className="w-4 h-4 inline mr-1"/>Enriched</TableHead>
                <TableHead className="text-right text-hot font-medium">HOT</TableHead>
                <TableHead className="text-right text-warm font-medium">WARM</TableHead>
                <TableHead className="text-right text-cold font-medium">COLD</TableHead>
                <TableHead className="text-right text-green font-medium"><MessageSquare className="w-4 h-4 inline mr-1"/>Pushed</TableHead>
                <TableHead className="text-right text-muted-foreground font-medium pr-6">Duration</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground py-10 font-mono">
                    Fetching runtime history from Python API...
                  </TableCell>
                </TableRow>
              )}
              {!loading && history.length === 0 && (
                 <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground py-10 font-mono">
                    No run logs detected.
                  </TableCell>
                </TableRow>
              )}
              {history.map((run, i) => (
                <TableRow key={i} className={`border-border/50 transition-colors ${run.current ? 'bg-primary/5 hover:bg-primary/10' : 'hover:bg-surface-2/50'}`}>
                  <TableCell className="font-medium text-white pl-6">
                    <div className="flex items-center">
                      {run.current && <span className="w-2 h-2 rounded-full bg-green animate-pulse inline-block mr-2" />}
                      {run.date}
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">{run.scraped}</TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">{run.filtered}</TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">{run.enriched}</TableCell>
                  <TableCell className="text-right font-mono text-white font-bold">{run.hot}</TableCell>
                  <TableCell className="text-right font-mono text-white">{run.warm}</TableCell>
                  <TableCell className="text-right font-mono text-muted-foreground">{run.cold}</TableCell>
                  <TableCell className="text-right font-mono text-green font-bold">{run.pushed}</TableCell>
                  <TableCell className="text-right text-muted-foreground pr-6 text-xs">{run.duration}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Middle Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Leads Per Day */}
        <Card className="bg-surface border-border/50">
          <CardHeader>
            <CardTitle className="font-display">Leads Per Day</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={DAILY_LEADS} margin={{ top: 10, right: 10, left: -20, bottom: 0 }} barSize={12}>
                  <XAxis dataKey="day" stroke="#475569" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#1e2d45', borderRadius: '8px' }}
                    itemStyle={{ color: '#f1f5f9' }}
                    cursor={{fill: '#1a2235'}}
                  />
                  <Bar dataKey="hot" stackId="a" fill="#ef4444" radius={[0, 0, 4, 4]} />
                  <Bar dataKey="warm" stackId="a" fill="#f59e0b" />
                  <Bar dataKey="cold" stackId="a" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Score Distribution */}
        <Card className="bg-surface border-border/50">
          <CardHeader>
            <CardTitle className="font-display">Score Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={SCORE_DISTRIBUTION} margin={{ top: 10, right: 10, left: -20, bottom: 0 }} barSize={24}>
                  <XAxis dataKey="score" stroke="#475569" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#1e2d45', borderRadius: '8px' }}
                    itemStyle={{ color: '#f1f5f9' }}
                    cursor={{fill: '#1a2235'}}
                  />
                  <Bar dataKey="count" fill="#7c3aed" radius={[4, 4, 0, 0]}>
                    {SCORE_DISTRIBUTION.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Step Breakdown */}
      <h3 className="font-display font-medium text-lg mt-8 mb-4">Pipeline Step Breakdown</h3>
      <div className="flex flex-wrap items-center gap-2 lg:gap-3 hide-scrollbar overflow-x-auto pb-4">
        {PIPELINE_STEPS.map((step, index) => (
          <div key={step.id} className="flex items-center">
            
            <div className="bg-surface border border-border/50 rounded-lg p-3 min-w-[140px] flex flex-col items-center justify-center text-center shadow-sm relative group hover:bg-surface-2 hover:border-border transition-colors">
              <div className="absolute top-2 left-2 flex">
                {step.done ? (
                  <CheckCircle2 className="w-4 h-4 text-green" />
                ) : (
                  <div className="w-4 h-4 rounded-full border-2 border-muted-foreground mr-1" />
                )}
              </div>
              <span className="text-[10px] text-muted-foreground font-mono mt-1 w-full text-right absolute top-2 right-2">#{step.id}</span>
              
              <span className="text-sm font-medium mt-3 mb-1">{step.name}</span>
              <span className={step.name.includes("Hot") || step.name.includes("Push") ? "text-primary font-bold text-xs" : "text-muted-foreground text-xs"}>
                {step.result}
              </span>
            </div>

            {index !== PIPELINE_STEPS.length - 1 && (
              <ArrowRight className="w-5 h-5 text-border mx-1 lg:mx-2 hidden sm:block flex-shrink-0" />
            )}
          </div>
        ))}
      </div>

    </div>
  );
}
