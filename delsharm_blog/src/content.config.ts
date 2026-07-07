import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders'; // <-- We must import the loader

const blog = defineCollection({
    // 1. Tell Astro exactly where to load the files from
    loader: glob({ pattern: '**/*.{md,mdx}', base: "./src/content/blog" }),
    
    // 2. Define our custom rules so it doesn't crash on your files
    schema: z.object({
        title: z.string(),
        date: z.coerce.date(),
        jalaliDate: z.string().optional(),
        tags: z.array(z.string()).optional(),
    }),
});

export const collections = { blog };