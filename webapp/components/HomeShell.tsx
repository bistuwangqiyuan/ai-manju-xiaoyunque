'use client';

/**
 * HomeShell — 客户端容器，桥接 SampleGallery → GeneratorForm
 * (sample 点击复用 prompt 触发 form ref API)
 */
import { useRef } from 'react';
import { GeneratorForm, type GeneratorFormHandle } from './GeneratorForm';
import { SampleGallery, type Sample } from './SampleGallery';

export function HomeShell() {
  const formRef = useRef<GeneratorFormHandle>(null);

  function handlePick(sample: Sample) {
    formRef.current?.setPromptFromSample(sample);
  }

  return (
    <>
      <section id="samples" className="px-6 pb-16">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-6">
            <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
              看看 AI 能做出什么
            </h2>
            <p className="mt-2 text-sm text-ink2">
              全部由 Skylark Agent 2.0 真实生成 · 100-pt rubric 实测评分
              <br />
              点击 <strong className="text-ink">"用此 prompt 生成同款"</strong> 即可复用模板
            </p>
          </div>
          <SampleGallery onPick={handlePick} />
        </div>
      </section>

      <section className="px-6 pb-12">
        <div className="text-center mb-6">
          <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
            轮到你了
          </h2>
          <p className="mt-2 text-sm text-ink2">
            注册账号 → 输入提示词 → 等约 5 分钟 → 收获 15 秒国漫短片
          </p>
        </div>
        <GeneratorForm ref={formRef} />
      </section>
    </>
  );
}
