export type PreviewView = "children" | "parents";

type PreviewCollection<T> = {
  children: T[];
  parents: T[];
};

export function chunksForPreviewView<T>(
  preview: PreviewCollection<T> | undefined,
  view: PreviewView,
): T[] {
  return preview?.[view] ?? [];
}
