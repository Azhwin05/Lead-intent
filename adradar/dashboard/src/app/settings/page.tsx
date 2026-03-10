"use client";

import { useState, useEffect } from "react";
import { Save, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { fetchHealthStatus, HealthStatus } from "@/lib/api";
import { toast } from "sonner";

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [checking, setChecking] = useState(true);

  const checkHealth = () => {
    setChecking(true);
    fetchHealthStatus().then((h) => {
      setHealth(h);
      setChecking(false);
    });
  };

  useEffect(() => {
    checkHealth();
  }, []);

  // Whether the overall Python backend is online
  const backendOnline = health?.status === "online";
  const airtableOk = health?.airtable === "connected";

  return (
    <div className="space-y-8 pb-10 animate-in fade-in duration-500 max-w-5xl mx-auto">
      
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-bold text-2xl text-white">System Configuration</h2>
          <p className="text-muted-foreground mt-1 text-sm">Manage pipelines, API keys, and tuning parameters</p>
        </div>
        <Button className="bg-primary hover:bg-primary/90 text-white shadow-lg" onClick={() => toast.success("Settings saved!")}>
          <Save className="w-4 h-4 mr-2" />
          Save Changes
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* API Status Block */}
        <Card className="bg-surface border-border/50 md:col-span-2">
          <CardHeader className="flex flex-row items-start justify-between">
            <div>
              <CardTitle className="font-display">API Connections</CardTitle>
              <CardDescription>Live status of your connected services</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={checkHealth} disabled={checking}
              className="border-border text-muted-foreground hover:text-white text-xs h-8">
              <RefreshCw className={`w-3 h-3 mr-2 ${checking ? "animate-spin" : ""}`} />
              {checking ? "Checking..." : "Re-check"}
            </Button>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              
              {/* Python Backend — live status */}
              <div className={`bg-surface-2 p-3 rounded-md border flex items-center justify-between transition-colors ${backendOnline ? "border-green/30" : "border-destructive/30"}`}>
                <div>
                  <span className="text-sm font-medium block">Python Backend</span>
                  <span className="text-[10px] text-muted-foreground font-mono">localhost:8000</span>
                </div>
                {checking ? (
                  <RefreshCw className="w-4 h-4 text-muted-foreground animate-spin" />
                ) : backendOnline ? (
                  <CheckCircle2 className="w-4 h-4 text-green" />
                ) : (
                  <XCircle className="w-4 h-4 text-destructive" />
                )}
              </div>
              
              {/* Airtable — live status */}
              <div className={`bg-surface-2 p-3 rounded-md border flex items-center justify-between transition-colors ${airtableOk ? "border-green/30" : "border-destructive/30"}`}>
                <div>
                  <span className="text-sm font-medium block">Airtable</span>
                  <span className="text-[10px] text-muted-foreground font-mono">{health?.airtable || "..."}</span>
                </div>
                {checking ? (
                  <RefreshCw className="w-4 h-4 text-muted-foreground animate-spin" />
                ) : airtableOk ? (
                  <CheckCircle2 className="w-4 h-4 text-green" />
                ) : (
                  <XCircle className="w-4 h-4 text-destructive" />
                )}
              </div>
              
              {/* Meta Ads — configured via .env */}
              <div className="bg-surface-2 p-3 rounded-md border border-green/30 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium block">Meta Ads</span>
                  <span className="text-[10px] text-muted-foreground font-mono">.env configured</span>
                </div>
                <CheckCircle2 className="w-4 h-4 text-green" />
              </div>
              
              {/* Apollo */}
              <div className="bg-surface-2 p-3 rounded-md border border-green/30 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium block">Apollo.io</span>
                  <span className="text-[10px] text-muted-foreground font-mono">.env configured</span>
                </div>
                <CheckCircle2 className="w-4 h-4 text-green" />
              </div>
              
              {/* Gemini */}
              <div className="bg-surface-2 p-3 rounded-md border border-green/30 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium block">Gemini API</span>
                  <span className="text-[10px] text-muted-foreground font-mono">.env configured</span>
                </div>
                <CheckCircle2 className="w-4 h-4 text-green" />
              </div>
              
              {/* Instantly */}
              <div className="bg-surface-2 p-3 rounded-md border border-green/30 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium block">Instantly.ai</span>
                  <span className="text-[10px] text-muted-foreground font-mono">.env configured</span>
                </div>
                <CheckCircle2 className="w-4 h-4 text-green" />
              </div>
              
              {/* Slack */}
              <div className="bg-surface-2 p-3 rounded-md border border-green/30 flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium block">Slack</span>
                  <span className="text-[10px] text-muted-foreground font-mono">.env configured</span>
                </div>
                <CheckCircle2 className="w-4 h-4 text-green" />
              </div>

              {/* Google Sheets */}
              <div className="bg-surface-2 p-3 rounded-md border border-destructive/30 flex items-center justify-between">
                <div>
                  <span className="text-sm text-muted-foreground block">Google Sheets</span>
                  <span className="text-[10px] text-muted-foreground font-mono">not configured</span>
                </div>
                <XCircle className="w-4 h-4 text-destructive" />
              </div>

            </div>
          </CardContent>
        </Card>

        {/* Pipeline Config */}
        <Card className="bg-surface border-border/50">
          <CardHeader>
            <CardTitle className="font-display">Pipeline Tuning</CardTitle>
            <CardDescription>Core logic variables for the daily scrape</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-white">Keywords (Comma separated)</label>
              <Input defaultValue="skincare, supplements, haircare, pets" className="bg-background border-border" />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-white">Min Days Running</label>
                <Input type="number" defaultValue="30" className="bg-background border-border" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-white">Schedule Time</label>
                <Input type="time" defaultValue="06:00" className="bg-background border-border" />
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium text-white">Minimum HOT Score Threshold</label>
                <Badge className="font-mono bg-primary">{7}</Badge>
              </div>
              <Slider defaultValue={[7]} max={10} step={1} className="py-2" />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-white">Target Country</label>
              <Select defaultValue="uk">
                <SelectTrigger className="bg-background border-border">
                  <SelectValue placeholder="Select Country" />
                </SelectTrigger>
                <SelectContent className="bg-surface border-border">
                  <SelectItem value="uk">United Kingdom</SelectItem>
                  <SelectItem value="us">United States</SelectItem>
                  <SelectItem value="ca">Canada</SelectItem>
                  <SelectItem value="au">Australia</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Right column */}
        <div className="space-y-6">
          <Card className="bg-surface border-border/50">
            <CardHeader>
              <CardTitle className="font-display">Scoring Weights</CardTitle>
              <CardDescription>Adjust the importance of AI signals</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {[
                { label: "S1: Creative Fatigue", color: "bg-hot" },
                { label: "S2: Desperation Testing", color: "bg-warm" },
                { label: "S3: Copy Quality", color: "bg-primary" },
                { label: "S4: Paid Traffic Dep", color: "bg-green" },
                { label: "S5: Team Size Risk", color: "bg-cold" },
              ].map((sig, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-muted-foreground">{sig.label}</span>
                    <span className="font-mono">2.0</span>
                  </div>
                  <Slider defaultValue={[2]} max={4} step={0.5} className="py-1" />
                </div>
              ))}
              <div className="p-3 bg-surface-2 rounded-md border border-border text-center text-sm font-medium text-muted-foreground">
                Current max score: <span className="font-mono text-white">10.0</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-surface border-border/50">
            <CardHeader>
              <CardTitle className="font-display">Agency Branding</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground">Agency Name</label>
                  <Input defaultValue="Firestone Media" className="bg-background border-border h-8 text-sm" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground">Sender Name</label>
                  <Input defaultValue="Alex" className="bg-background border-border h-8 text-sm" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground">Case Study Brand</label>
                  <Input defaultValue="Glowup Skincare" className="bg-background border-border h-8 text-sm" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs text-muted-foreground">Case Study Result</label>
                  <Input defaultValue="620% ROAS in 6 weeks" className="bg-background border-border h-8 text-sm" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

      </div>
    </div>
  );
}
