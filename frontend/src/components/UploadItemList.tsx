import { UploadItem } from "../api/client";

type Props = {
  items: UploadItem[];
};

export function UploadItemList({ items }: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>上传队列</h2>
        <span>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="empty">暂无广告上传项。</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              <th>类型</th>
              <th>素材</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.item_order}</td>
                <td>{item.requested_name}</td>
                <td>{item.requested_type}</td>
                <td>{item.local_asset_query || "-"}</td>
                <td><span className={`pill ${item.status}`}>{item.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
