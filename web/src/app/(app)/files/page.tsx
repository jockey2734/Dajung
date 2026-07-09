import { FilesClient } from "@/components/files/files-client";

export default function FilesPage() {
  return (
    <main className="flex h-full flex-col overflow-y-auto bg-surface-soft">
      <FilesClient />
    </main>
  );
}
