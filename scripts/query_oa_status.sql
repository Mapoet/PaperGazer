-- 查询数据库中的OA状态信息
-- 在数据库工具中执行此SQL可以查看Unpaywall查询结果

-- 查看所有有OA信息的记录
SELECT 
    id,
    source,
    substr(title, 1, 50) as title,
    doi,
    is_oa,
    oa_source,
    oa_pdf_url,
    published_date,
    updated_date
FROM items
WHERE oa_source IS NOT NULL
ORDER BY updated_date DESC;

-- 统计信息
SELECT 
    COUNT(*) as total_records,
    COUNT(CASE WHEN doi IS NOT NULL AND doi != '' THEN 1 END) as with_doi,
    COUNT(CASE WHEN is_oa = 1 THEN 1 END) as is_oa_count,
    COUNT(CASE WHEN oa_source = 'unpaywall' THEN 1 END) as unpaywall_count
FROM items;

-- 查看有DOI但还没有OA信息的记录
SELECT 
    id,
    source,
    substr(title, 1, 50) as title,
    doi,
    published_date
FROM items
WHERE doi IS NOT NULL 
  AND doi != ''
  AND oa_source IS NULL
ORDER BY updated_date DESC;

