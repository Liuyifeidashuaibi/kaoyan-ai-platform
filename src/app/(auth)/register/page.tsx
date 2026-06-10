import { Suspense } from "react";

import { RegisterForm } from "@/components/auth/register-form";

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="text-center text-sm text-muted-foreground">加载中...</div>}>
      <RegisterForm />
    </Suspense>
  );
}
