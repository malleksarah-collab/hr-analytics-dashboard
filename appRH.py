import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title='HR Analytics', layout='wide')
TEAL = '#00D9D0'
PURPLE = '#AD7AFF'
COLORS = {'Male': TEAL, 'Female': PURPLE}

@st.cache_data
def load_data():
    df = pd.read_excel(Path(__file__).parent / 'employee.xlsx')
    df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
    df = df.drop_duplicates('id')
    df = df[df['salary'] > 0].copy()
    df['hire_year'] = df['start_date'].dt.year
    return df

df = load_data()
st.sidebar.title('HR Analytics')
st.sidebar.caption('Employee Compensation Project')
st.sidebar.markdown('**Business objective**')
st.sidebar.write('Understand workforce composition, compensation and pay equity to support HR decisions.')
page = st.sidebar.radio('Navigation', ['Overview', 'Workforce Analysis', 'Compensation Analysis', 'Pay Equity Analysis'], key='page')
st.sidebar.divider()
st.sidebar.header('Filters')
if st.sidebar.button('Reset filters', use_container_width=True):
    for key in ['department', 'gender', 'region', 'year', 'salary']:
        st.session_state.pop(key, None)
    st.rerun()

departments = st.sidebar.multiselect('Department', sorted(df.department.unique()), key='department')
genders = st.sidebar.multiselect('Gender', sorted(df.gender.unique()), key='gender')
regions = st.sidebar.multiselect('Region', sorted(df.region_id.unique()), key='region')
years = (int(df.hire_year.min()), int(df.hire_year.max()))
salaries = (int(df.salary.min()), int(df.salary.max()))
year = st.sidebar.slider('Hire year', *years, years, key='year')
salary = st.sidebar.slider('Salary range', *salaries, salaries, key='salary')
st.sidebar.caption('Empty category selection = all categories.')

# Apply filters
filtered = df[df.hire_year.between(*year) & df.salary.between(*salary)].copy()
for column, selected in [('department', departments), ('gender', genders), ('region_id', regions)]:
    if selected:
        filtered = filtered[filtered[column].isin(selected)]

st.title('Workforce & Salary Intelligence')
st.caption('Executive overview of headcount, compensation and pay equity. Salary currency and pay period are not documented.')
if filtered.empty:
    st.warning('No employees match the selected filters.')
    st.stop()

# Executive KPIs
metrics = st.columns(5)
for col, label, value in zip(metrics,
    ['Employees', 'Average salary', 'Median salary', 'Total recorded salary', 'Departments'],
    [f'{filtered.id.nunique():,}', f'{filtered.salary.mean():,.0f}',
     f'{filtered.salary.median():,.0f}', f'{filtered.salary.sum()/1e6:,.2f}M',
     str(filtered.department.nunique())]):
    col.metric(label, value, border=True)

# Aggregations from the EDA
hires = filtered.groupby('hire_year').size().reindex(range(year[0], year[1]+1), fill_value=0).rename('employees').reset_index()
dep = filtered.groupby('department').salary.agg(['mean', 'count']).reset_index()
region = filtered.groupby('region_id').salary.mean().reset_index()
region['region_id'] = region.region_id.astype(str)
cohort = filtered.groupby('hire_year').salary.mean().reset_index()
gender = filtered.gender.value_counts().rename_axis('gender').reset_index(name='employees')
comparison = filtered.groupby(['department', 'gender']).salary.agg(['mean', 'count']).reset_index()
pivot = filtered.pivot_table(index='department', columns='gender', values='salary', aggfunc='mean').reindex(columns=['Male', 'Female'])
pivot['gap'] = (pivot.Male - pivot.Female) / pivot.Male * 100
gap = pivot[['gap']].dropna().sort_values('gap', ascending=False)

# Shared chart style
def chart(fig, height=320):
    fig.update_layout(template='plotly_dark', paper_bgcolor='#080808', plot_bgcolor='#080808',
                      font_color='#E8E8E8', height=height, margin=dict(l=15,r=15,t=45,b=15),
                      legend_title_text='', title_font_size=16)
    fig.update_xaxes(gridcolor='#242424')
    fig.update_yaxes(gridcolor='#242424')
    st.plotly_chart(fig, width="stretch")


def hires_chart():
    chart(px.line(hires, x='hire_year', y='employees', markers=True,
                  title='Recorded hires by year', color_discrete_sequence=[TEAL],
                  labels={'hire_year':'Hire year', 'employees':'Employees'}))


def top_chart():
    top = dep.nlargest(5, 'mean').sort_values('mean')
    chart(px.bar(top, x='mean', y='department', orientation='h',
                 title='Top 5 departments by average salary', color_discrete_sequence=[TEAL],
                 hover_data=['count'], labels={'mean':'Average salary','department':'Department'}))


def gender_chart():
    chart(px.pie(gender, names='gender', values='employees', hole=.65, color='gender',
                 color_discrete_map=COLORS, title='Gender composition'))


def region_chart():
    chart(px.bar(region, x='region_id', y='salary', title='Average salary by region',
                 color_discrete_sequence=[TEAL], labels={'region_id':'Region','salary':'Average salary'}))


def cohort_chart():
    chart(px.line(cohort, x='hire_year', y='salary', markers=True,
                  title='Average salary by hire year', color_discrete_sequence=[TEAL],
                  labels={'hire_year':'Hire year','salary':'Average salary'}))


def comparison_chart():
    chart(px.bar(comparison, x='mean', y='department', color='gender', barmode='group',
                 orientation='h', color_discrete_map=COLORS, hover_data=['count'],
                 title='Average salary by department and gender',
                 labels={'mean':'Average salary','department':'Department'}), 650)


def gap_chart():
    if gap.empty:
        st.info('Pay gap requires both gender groups within a department.')
        return
    limit = max(float(gap.gap.abs().max()), 1)
    chart(px.imshow(gap, text_auto='.1f', color_continuous_scale='RdBu_r',
                    range_color=[-limit, limit], aspect='auto',
                    title='Gender pay gap by department (%)',
                    labels={'color':'Gap (%)','y':'Department','x':''}), 650)
    st.caption('Positive: higher male mean. Negative: higher female mean. Unadjusted comparison.')


def insights():
    st.subheader('Decision Insights')
    top = dep.loc[dep['mean'].idxmax()]
    st.write(f"**Compensation:** {top.department} has the highest average salary ({top['mean']:,.0f}; n={int(top['count'])}).")
    peak = hires.loc[hires.employees.idxmax()]
    st.write(f"**Workforce:** {int(peak.hire_year)} is the most represented hire year ({int(peak.employees)} employees).")
    if not gap.empty:
        name = gap.gap.abs().idxmax()
        st.write(f'**Pay equity:** {name} has the largest absolute unadjusted gap ({gap.loc[name, "gap"]:+.1f}%). Review comparable roles and group sizes before acting.')
    else:
        st.write('**Pay equity:** insufficient comparable gender groups in this selection.')
    st.caption('Descriptive associations only. Hire cohorts are not historical headcount or salary trends.')

# Navigation and dashboard layout
if page == 'Overview':
    a, b = st.columns([1.3, 1])
    with a: hires_chart()
    with b: top_chart()
    a, b, c = st.columns(3)
    with a: gender_chart()
    with b: region_chart()
    with c: cohort_chart()
    st.subheader('Multivariate Analysis')
    a, b, c = st.columns([1.4, 1, 1])
    with a: comparison_chart()
    with b: gap_chart()
    with c: insights()
elif page == 'Workforce Analysis':
    a, b = st.columns(2)
    with a: hires_chart()
    with b: gender_chart()
    chart(px.bar(dep.sort_values('count'), x='count', y='department', orientation='h', title='Employees by department', color_discrete_sequence=[TEAL]), 600)
elif page == 'Compensation Analysis':
    a, b = st.columns(2)
    with a: top_chart()
    with b: region_chart()
    cohort_chart()
    chart(px.scatter(filtered, x='start_date', y='salary', color='gender', color_discrete_map=COLORS, opacity=.55, title='Hire date vs salary by gender'))
else:
    a, b = st.columns(2)
    with a: comparison_chart()
    with b: gap_chart()
    st.dataframe(comparison.rename(columns={'mean':'Average salary','count':'Employees'}), hide_index=True)
    insights()
