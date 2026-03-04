/**
 * 黑塔树 - 社交平台前端应用
 * 深紫色主题，类似微博/X 的界面
 */

// API 基础地址
const API_BASE_URL = 'http://127.0.0.1:8006';

// 当前页面状态
let currentPage = 'home';
let currentUserId = null;
let currentSort = 'recommended'; // 默认排序：推荐算法

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    loadTimeline();
});

// ==================== 导航 ====================

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item a');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            switchPage(page);
            
            // 更新活跃状态
            navItems.forEach(nav => nav.parentElement.classList.remove('active'));
            item.parentElement.classList.add('active');
        });
    });
}

function switchPage(page) {
    currentPage = page;
    const title = document.querySelector('.page-title');
    const timeline = document.getElementById('timeline');
    
    switch(page) {
        case 'home':
            title.textContent = '首页';
            loadTimeline();
            break;
    }
}

// ==================== 数据加载 ====================

async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API 请求失败:', error);
        return null;
    }
}

// ==================== 时间线 ====================

async function loadTimeline() {
    const timeline = document.getElementById('timeline');
    timeline.innerHTML = '<div class="loading"><div class="spinner"></div>加载中...</div>';
    
    const posts = await fetchAPI(`/posts?limit=20&sort=${currentSort}`);
    if (!posts || posts.length === 0) {
        timeline.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📝</div>
                <div class="empty-text">暂无帖子</div>
            </div>
        `;
        return;
    }
    
    timeline.innerHTML = posts.map(post => createPostCard(post)).join('');
}

function createPostCard(post) {
    const avatar = post.author?.avatar || '/avatar/Avatar.png';
    const username = post.author?.username || '未知用户';
    const bio = post.author?.bio || '';
    const time = formatTime(post.created_at);
    const likesCount = post.likes_count || 0;
    const likers = post.likers || [];
    
    return `
        <div class="post-card" id="post-${post.id}">
            <div class="post-header">
                <img src="${API_BASE_URL}${avatar}" alt="${username}" class="avatar" onerror="this.onerror=null; this.src='${API_BASE_URL}/avatar/Avatar.png'">
                <div class="post-meta">
                    <a href="#" class="username" onclick="event.stopPropagation(); showUserDetail(${post.author_id})">${username}</a>
                    ${bio ? `<div class="post-bio">${escapeHtml(bio)}</div>` : ''}
                    <div class="post-time">${time}</div>
                </div>
            </div>
            <div class="post-content">${escapeHtml(post.content)}</div>
            ${likers.length > 0 ? `
                <div class="post-likers">
                    ${likers.map(liker => `
                        <span class="liker-item" onclick="showUserDetail(${liker.id})">
                            <img src="${API_BASE_URL}${liker.avatar}" alt="${liker.username}" class="liker-avatar" onerror="this.onerror=null; this.src='${API_BASE_URL}/avatar/Avatar.png'">
                            <span class="liker-name">${escapeHtml(liker.username)}</span>
                        </span>
                    `).join('')}
                    ${likesCount > 3 ? `<span class="more-likers">等${likesCount}人点赞</span>` : '<span class="more-likers">赞了</span>'}
                </div>
            ` : ''}
            <div class="post-stats">
                <div class="stat-item likes">
                    <span class="stat-icon">❤️</span>
                    <span>${likesCount}</span>
                </div>
                <div class="stat-item comments" onclick="toggleComments(${post.id})">
                    <span class="stat-icon">💬</span>
                    <span>${post.comments_count || 0}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-icon">🔄</span>
                    <span>${post.reposts_count || 0}</span>
                </div>
            </div>
            <div class="post-comments-section" id="comments-${post.id}" style="display: none;">
                <div class="comments-loading">加载评论中...</div>
            </div>
        </div>
    `;
}

// ==================== 排序切换 ====================

function switchSort(sortType) {
    currentSort = sortType;
    
    // 更新按钮状态
    document.querySelectorAll('.sort-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.sort === sortType) {
            tab.classList.add('active');
        }
    });
    
    // 重新加载时间线
    loadTimeline();
}

// ==================== 评论展开/收起 ====================

async function toggleComments(postId) {
    const commentsSection = document.getElementById(`comments-${postId}`);
    
    if (!commentsSection) return;
    
    // 如果已经显示，则收起
    if (commentsSection.style.display === 'block') {
        commentsSection.style.display = 'none';
        return;
    }
    
    // 显示评论区域
    commentsSection.style.display = 'block';
    
    // 加载评论（使用热度混合排序）
    const comments = await fetchAPI(`/posts/${postId}/comments?mixed=true`) || [];
    
    if (comments.length === 0) {
        commentsSection.innerHTML = '<div class="empty-text" style="padding: 16px; color: #8899a6;">暂无评论</div>';
        return;
    }
    
    commentsSection.innerHTML = `
        <div class="comments-list">
            ${comments.map(comment => createCommentHTML(comment)).join('')}
        </div>
    `;
}

function createCommentHTML(comment) {
    const avatar = comment.author?.avatar || '/avatar/Avatar.png';
    const username = comment.author?.username || '未知用户';
    const time = formatTime(comment.created_at);
    const replies = comment.replies || [];
    
    return `
        <div class="comment-item">
            <img src="${API_BASE_URL}${avatar}" alt="${username}" class="avatar" onerror="this.onerror=null; this.src='${API_BASE_URL}/avatar/Avatar.png'">
            <div class="comment-content">
                <div class="comment-header">
                    <span class="comment-author">${username}</span>
                    <span class="comment-time">${time}</span>
                </div>
                <div class="comment-text">${escapeHtml(comment.content)}</div>
                <div class="comment-actions">
                    <span class="comment-action">❤️ ${comment.likes_count || 0}</span>
                    <span class="comment-action">💬 ${comment.replies_count || 0}</span>
                </div>
                ${replies.length > 0 ? `
                    <div class="replies">
                        ${replies.map((reply, index) => {
                            // 获取父级回复（如果是回复的回复）
                            const parentReply = reply.parent_reply_id && index > 0 
                                ? replies.find(r => r.id === reply.parent_reply_id) 
                                : null;
                            return createReplyHTML(reply, parentReply);
                        }).join('')}
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function createReplyHTML(reply, parentReply = null) {
    const avatar = reply.author?.avatar || '/avatar/Avatar.png';
    const username = reply.author?.username || '未知用户';
    const time = formatTime(reply.created_at);
    
    // 如果有父级回复，显示 "回复 @xxx"
    const replyToText = parentReply ? `回复 <span class="reply-to">@${escapeHtml(parentReply.author?.username || '用户')}</span>` : '';
    
    return `
        <div class="reply-item">
            <img src="${API_BASE_URL}${avatar}" alt="${username}" class="reply-avatar" onerror="this.onerror=null; this.src='${API_BASE_URL}/avatar/Avatar.png'">
            <div class="reply-content">
                <div class="reply-header">
                    <span class="reply-author">${username}</span>
                    <span class="reply-time">${time}</span>
                    ${replyToText ? `<span class="reply-to-text">${replyToText}</span>` : ''}
                </div>
                <div class="reply-text">${escapeHtml(reply.content)}</div>
            </div>
        </div>
    `;
}

async function showUserDetail(userId) {
    alert('用户详情功能开发中... 用户 ID: ' + userId);
}

// ==================== 工具函数 ====================

function search() {
    const query = document.getElementById('searchInput').value;
    if (!query) return;
    
    alert('搜索功能开发中...\n搜索关键词：' + query);
}

function formatTime(isoString) {
    if (!isoString) return '未知时间';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    
    // 小于 1 小时
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return minutes < 1 ? '刚刚' : `${minutes}分钟前`;
    }
    // 小于 24 小时
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}小时前`;
    }
    // 小于 7 天
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days}天前`;
    }
    
    return date.toLocaleDateString('zh-CN');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
