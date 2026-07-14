import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
    const blog = await getCollection('blog');
    
    // Sort posts so newest are at the top
    const sortedPosts = blog.sort((a, b) => new Date(b.data.date).getTime() - new Date(a.data.date).getTime());

    return rss({
        title: 'وب‌نوشت‌های دلشرم',
        description: 'یادداشت‌های محمدصادق رسولی',
        site: context.site, // Pulls 'https://rasoolims.github.io' from your config
        items: sortedPosts.map((post) => ({
            title: post.data.title,
            pubDate: new Date(post.data.date),
            description: post.data.jalaliDate || 'نوشته جدید در دلشرم', 
            // Crucial: Includes your repository subfolder path!
            link: `/delsharm/blog/${post.id}/`,
        })),
        customData: `<language>fa-IR</language>`,
    });
}