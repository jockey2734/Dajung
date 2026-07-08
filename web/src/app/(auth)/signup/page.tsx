import { SignupForm } from "@/components/auth/signup-form";

export default function SignupPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-cream px-6 py-10">
      <h1 className="text-display text-ink">Dajung AI</h1>
      <SignupForm />
    </div>
  );
}
