export interface FileEntry {
  doc_id: string;
  source_file: string;
  doc_type: string;
  semester: string | null;
  restricted: boolean;
  chunk_count: number;
}

export interface FileListResponse {
  files: FileEntry[];
}
