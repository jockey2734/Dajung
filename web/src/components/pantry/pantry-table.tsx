"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";
import { 
  ArrowDownIcon, 
  ArrowUpIcon, 
  MoreHorizontal, 
  Trash2,
  Check,
  X
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import type { PantryItemOut, PantryKind, PantryRemainingPct, SortField, OrderField } from "@/types/pantry";

function RemainingSegmentBar({ pct, isCoffee }: { pct: PantryRemainingPct, isCoffee: boolean }) {
  const blocks = pct / 25;
  const isWarning = isCoffee && pct <= 25;
  const isDanger = isCoffee && pct === 0;
  
  const colorClass = isDanger 
    ? "bg-semantic-error" 
    : isWarning 
      ? "bg-semantic-warning" 
      : "bg-espresso";
      
  return (
    <div className="flex gap-[2px]">
      {[1, 2, 3, 4, 5].map(i => (
        <div 
          key={i} 
          className={`h-2 w-4 rounded-sm ${i <= blocks ? colorClass : 'bg-muted-token'}`} 
        />
      ))}
    </div>
  )
}

function KindBadge({ kind }: { kind: PantryKind }) {
  const label = kind === "coffee" ? "커피" : kind === "tea" ? "차" : "기타";
  const bgClass = kind === "coffee" ? "bg-espresso text-cream" : kind === "tea" ? "bg-tea-green-soft text-tea-green" : "bg-surface text-taupe border border-hairline";
  
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-caption-bold ${bgClass}`}>
      {label}
    </span>
  );
}

interface PantryTableProps {
  items: PantryItemOut[];
  sort: SortField;
  order: OrderField;
  onSortChange: (field: SortField) => void;
  onUpdate: (id: string, updates: Partial<PantryItemOut>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onAdd: (item: { name: string; kind: PantryKind; remaining_pct: PantryRemainingPct; capacity_g: number | null; note: string | null }) => Promise<void>;
}

export function PantryTable({ items, sort, order, onSortChange, onUpdate, onDelete, onAdd }: PantryTableProps) {
  const [adding, setAdding] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  
  // New item state
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<PantryKind>("coffee");
  const [newPct, setNewPct] = useState<PantryRemainingPct>(100);
  const [newCapacity, setNewCapacity] = useState<string>("");
  const [newNote, setNewNote] = useState("");

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sort !== field) return null;
    return order === "asc" ? <ArrowUpIcon className="w-3 h-3 ml-1 inline" /> : <ArrowDownIcon className="w-3 h-3 ml-1 inline" />;
  };

  const handleAddSubmit = async () => {
    if (!newName.trim()) return;
    await onAdd({
      name: newName,
      kind: newKind,
      remaining_pct: newPct,
      capacity_g: newCapacity ? parseInt(newCapacity, 10) : null,
      note: newNote || null,
    });
    setAdding(false);
    setNewName("");
    setNewCapacity("");
    setNewNote("");
  };

  const handleDeleteConfirm = async () => {
    if (deleteId) {
      await onDelete(deleteId);
      setDeleteId(null);
    }
  };

  return (
    <>
      <div className="w-full overflow-x-auto rounded-md border border-hairline bg-canvas">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-surface text-caption-bold text-taupe border-b border-hairline">
              <th 
                className="px-4 py-3 cursor-pointer hover:bg-surface-soft"
                onClick={() => onSortChange("name")}
              >
                이름 <SortIcon field="name" />
              </th>
              <th className="px-4 py-3">종류</th>
              <th 
                className="px-4 py-3 cursor-pointer hover:bg-surface-soft"
                onClick={() => onSortChange("remaining_pct")}
              >
                남은 양 <SortIcon field="remaining_pct" />
              </th>
              <th className="px-4 py-3">용량(g)</th>
              <th className="px-4 py-3">메모</th>
              <th 
                className="px-4 py-3 cursor-pointer hover:bg-surface-soft"
                onClick={() => onSortChange("updated_at")}
              >
                수정 <SortIcon field="updated_at" />
              </th>
              <th className="px-4 py-3 w-10"></th>
            </tr>
          </thead>
          <tbody className="text-body-sm">
            {items.map((item) => (
              <EditableRow 
                key={item.id} 
                item={item} 
                onUpdate={(updates) => onUpdate(item.id, updates)} 
                onDeleteRequest={() => setDeleteId(item.id)} 
              />
            ))}
            
            {adding && (
              <tr className="border-b border-hairline bg-surface-soft/50">
                <td className="px-4 py-2">
                  <Input 
                    value={newName} 
                    onChange={e => setNewName(e.target.value)} 
                    placeholder="이름" 
                    className="h-8"
                    autoFocus
                  />
                </td>
                <td className="px-4 py-2">
                  <select 
                    value={newKind} 
                    onChange={e => setNewKind(e.target.value as PantryKind)}
                    className="h-8 rounded-md border border-input bg-canvas px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="coffee">커피</option>
                    <option value="tea">차</option>
                    <option value="other">기타</option>
                  </select>
                </td>
                <td className="px-4 py-2">
                  <select 
                    value={newPct} 
                    onChange={e => setNewPct(parseInt(e.target.value) as PantryRemainingPct)}
                    className="h-8 rounded-md border border-input bg-canvas px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value={100}>100%</option>
                    <option value={75}>75%</option>
                    <option value={50}>50%</option>
                    <option value={25}>25%</option>
                    <option value={0}>0%</option>
                  </select>
                </td>
                <td className="px-4 py-2">
                  <Input 
                    value={newCapacity} 
                    onChange={e => setNewCapacity(e.target.value)} 
                    placeholder="ex: 250" 
                    type="number"
                    className="h-8 w-20"
                    disabled={newKind !== "coffee"}
                  />
                </td>
                <td className="px-4 py-2">
                  <Input 
                    value={newNote} 
                    onChange={e => setNewNote(e.target.value)} 
                    placeholder="메모" 
                    className="h-8"
                  />
                </td>
                <td className="px-4 py-2 text-taupe text-caption">저장 대기</td>
                <td className="px-4 py-2">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-semantic-success" onClick={handleAddSubmit}><Check className="w-4 h-4"/></Button>
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-taupe" onClick={() => setAdding(false)}><X className="w-4 h-4"/></Button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
        
        {!adding && (
          <div className="p-2 flex justify-center border-t border-hairline bg-canvas">
            <Button variant="ghost" size="sm" onClick={() => setAdding(true)} className="text-taupe hover:text-espresso">
              + 항목 추가
            </Button>
          </div>
        )}
      </div>

      <Dialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>항목 삭제</DialogTitle>
            <DialogDescription>
              정말 이 항목을 삭제하시겠습니까? 복구할 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>취소</Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>삭제</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function EditableRow({ 
  item, 
  onUpdate, 
  onDeleteRequest 
}: { 
  item: PantryItemOut, 
  onUpdate: (u: Partial<PantryItemOut>) => void,
  onDeleteRequest: () => void 
}) {
  const [name, setName] = useState(item.name);
  const [note, setNote] = useState(item.note || "");
  const [capacity, setCapacity] = useState(item.capacity_g?.toString() || "");

  const handleBlur = (field: keyof PantryItemOut, value: any) => {
    if (item[field] !== value && !(item[field] === null && value === "")) {
      onUpdate({ [field]: value === "" ? null : value });
    }
  };

  const timeStr = formatDistanceToNow(new Date(item.updated_at), { addSuffix: true, locale: ko });

  return (
    <tr className="border-b border-hairline hover:bg-surface-soft/50 transition-colors group">
      <td className="px-4 py-2">
        <Input 
          value={name}
          onChange={e => setName(e.target.value)}
          onBlur={() => handleBlur("name", name)}
          className="h-8 border-transparent bg-transparent hover:border-input focus:bg-canvas"
        />
      </td>
      <td className="px-4 py-2">
        <select 
          value={item.kind}
          onChange={e => onUpdate({ kind: e.target.value as PantryKind })}
          className="h-8 bg-transparent text-sm cursor-pointer outline-none"
        >
          <option value="coffee">커피</option>
          <option value="tea">차</option>
          <option value="other">기타</option>
        </select>
      </td>
      <td className="px-4 py-2">
        <div className="flex items-center gap-2">
          <RemainingSegmentBar pct={item.remaining_pct} isCoffee={item.kind === "coffee"} />
          <select 
            value={item.remaining_pct}
            onChange={e => onUpdate({ remaining_pct: parseInt(e.target.value) as PantryRemainingPct })}
            className="bg-transparent text-sm cursor-pointer outline-none font-mono"
          >
            <option value={100}>100%</option>
            <option value={75}>75%</option>
            <option value={50}>50%</option>
            <option value={25}>25%</option>
            <option value={0}>0%</option>
          </select>
          {item.kind === "coffee" && item.estimated_g !== null && (
            <span className="text-caption text-taupe ml-1">{item.estimated_g}g</span>
          )}
        </div>
      </td>
      <td className="px-4 py-2">
        <Input 
          value={capacity}
          onChange={e => setCapacity(e.target.value)}
          onBlur={() => handleBlur("capacity_g", capacity ? parseInt(capacity, 10) : null)}
          className="h-8 w-20 border-transparent bg-transparent hover:border-input focus:bg-canvas"
          disabled={item.kind !== "coffee"}
          type="number"
        />
      </td>
      <td className="px-4 py-2">
        <Input 
          value={note}
          onChange={e => setNote(e.target.value)}
          onBlur={() => handleBlur("note", note)}
          className="h-8 border-transparent bg-transparent hover:border-input focus:bg-canvas"
          placeholder="-"
        />
      </td>
      <td className="px-4 py-2 text-caption text-taupe whitespace-nowrap">
        {item.updated_by.name} · {timeStr}
      </td>
      <td className="px-4 py-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-taupe hover:text-espresso">
              <MoreHorizontal className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onDeleteRequest} className="text-semantic-error focus:text-semantic-error focus:bg-semantic-error-soft">
              <Trash2 className="w-4 h-4 mr-2" /> 삭제
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </td>
    </tr>
  );
}
