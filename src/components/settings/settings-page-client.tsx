"use client";

import Link from "next/link";
import { Loader2, Mail } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getUserSettings, updateUserSettings } from "@/lib/api/settings";

export function SettingsPageClient() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [email, setEmail] = useState("");
  const [deliveryConfigured, setDeliveryConfigured] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const settings = await getUserSettings();
        setEmail(settings.translation_download_email ?? "");
        setDeliveryConfigured(settings.email_delivery_configured);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load settings");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const settings = await updateUserSettings({
        translation_download_email: email.trim() || null,
      });
      setEmail(settings.translation_download_email ?? "");
      setDeliveryConfigured(settings.email_delivery_configured);
      setMessage("Saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Loading settings…
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Module preferences for your account. More sections will appear here over time.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Mail className="size-5" />
            Translator
          </CardTitle>
          <CardDescription>
            Translation exports (Word, PDF, or plain text) are emailed to this address
            instead of downloading in the browser.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="translation-download-email">Download email</Label>
            <Input
              id="translation-download-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <p className="text-muted-foreground text-xs">
              Can differ from your login email. Leave empty to disable email export.
            </p>
          </div>

          {!deliveryConfigured ? (
            <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
              Server email delivery is not configured yet (SMTP). Bind your email here first;
              ask the operator to set{" "}
              <code className="text-[11px]">SMTP_HOST</code> and{" "}
              <code className="text-[11px]">SMTP_FROM</code> in{" "}
              <code className="text-[11px]">.env</code>. Recommended: Resend, Brevo, or
              SendGrid — no custom domain required for testing.
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void handleSave()} disabled={saving}>
              {saving ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
              Save
            </Button>
            {message ? (
              <span className="text-sm text-emerald-600 dark:text-emerald-400">{message}</span>
            ) : null}
            {error ? (
              <span className="text-destructive text-sm">{error}</span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-xs">
        <Link href="/profile" className="underline underline-offset-2 hover:text-foreground">
          Back to profile
        </Link>
      </p>
    </div>
  );
}
