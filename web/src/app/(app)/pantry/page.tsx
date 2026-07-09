import { PantryClient } from "@/components/pantry/pantry-client";

export default function PantryPage() {
  return (
    <main className="flex flex-col h-full overflow-y-auto bg-surface-soft">
      <PantryClient />
    </main>
  );
}
