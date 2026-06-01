export default function DealCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-hidden flex flex-col h-full">
      <div className="h-48 bg-gradient-to-br from-gray-100 to-gray-200 animate-pulse" />
      <div className="p-4 flex flex-col gap-2 flex-grow">
        <div className="h-3 bg-gray-200 rounded animate-pulse w-full" />
        <div className="h-3 bg-gray-200 rounded animate-pulse w-4/5" />
        <div className="h-3 bg-gray-200 rounded animate-pulse w-3/5" />
        <div className="mt-auto pt-3">
          <div className="h-6 bg-gray-200 rounded animate-pulse w-1/2 mb-2" />
          <div className="h-2 bg-gray-100 rounded animate-pulse w-full" />
        </div>
      </div>
    </div>
  );
}

export function DealGridSkeleton({ count = 9 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <DealCardSkeleton key={i} />
      ))}
    </div>
  );
}
