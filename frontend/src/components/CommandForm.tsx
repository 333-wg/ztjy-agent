import { FormEvent, useState } from "react";

type Props = {
  loading: boolean;
  onSubmit: (command: string) => Promise<void>;
};

export function CommandForm({ loading, onSubmit }: Props) {
  const [command, setCommand] = useState("给设备 10086 添加 May promo video");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!command.trim()) return;
    await onSubmit(command.trim());
  }

  return (
    <form className="command-panel" onSubmit={submit}>
      <label htmlFor="command">自然语言命令</label>
      <textarea
        id="command"
        value={command}
        onChange={(event) => setCommand(event.target.value)}
        rows={7}
      />
      <button type="submit" disabled={loading}>
        {loading ? "执行中" : "创建任务"}
      </button>
    </form>
  );
}
